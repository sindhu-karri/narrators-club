"""
Combined CI script: scrapes member roster + fetches Base Camp completions.
- Uses Chrome headless (GitHub Actions Ubuntu runner)
- Credentials from TM_EMAIL / TM_PASSWORD env vars
- Reads member_overrides.json for mentors / join dates (safe to commit, no GUIDs)
- Outputs member_modals.json and member_courses.json (both gitignored)

Run order in workflow:
  python fetch_ci.py        → member_modals.json + member_courses.json
  python generate_ci.py     → ../data.js
"""
import os, sys, re, time, json, requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Credentials ───────────────────────────────────────────────────────────────
email    = os.environ.get("TM_EMAIL", "").strip()
password = os.environ.get("TM_PASSWORD", "").strip()
if not email or not password:
    raise SystemExit("ERROR: TM_EMAIL and TM_PASSWORD environment variables must be set.")

# ── Club-specific overrides (mentors, join dates — no GUIDs) ──────────────────
overrides_path = os.path.join(SCRIPT_DIR, "member_overrides.json")
overrides = {}
if os.path.exists(overrides_path):
    with open(overrides_path, encoding="utf-8") as f:
        overrides = json.load(f)
    print(f"Loaded member_overrides.json ({len(overrides.get('mentors',{}))} mentors, "
          f"{len(overrides.get('new_members',{}))} new member overrides)")
else:
    print("No member_overrides.json found — proceeding without overrides")

# ── Browser setup ─────────────────────────────────────────────────────────────
def make_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=opts)

def force_close_modal(driver):
    driver.execute_script("""
        document.querySelectorAll('.modal-backdrop').forEach(e=>e.remove());
        document.querySelectorAll('.modal').forEach(e=>{
            e.style.display='none'; e.classList.remove('in','show');
        });
        document.body.classList.remove('modal-open');
        document.body.style.overflow='auto';
    """)
    time.sleep(0.5)

# ── Login ─────────────────────────────────────────────────────────────────────
print("Starting browser and logging in...", flush=True)
driver = make_driver()
wait   = WebDriverWait(driver, 30)

driver.get("https://www.toastmasters.org/myhome")
time.sleep(5)
wait.until(EC.presence_of_element_located((By.ID, "signInName"))).send_keys(email)
driver.find_element(By.ID, "password").send_keys(password)
driver.find_element(By.ID, "continue").click()
time.sleep(10)
print(f"Logged in: {driver.current_url[:70]}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — Scrape member roster from Club Membership page
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Scraping member roster ──────────────────────────────────────────", flush=True)
driver.get("https://www.toastmasters.org/my-toastmasters/profile/club-central/club-membership")
time.sleep(12)

src  = driver.page_source
soup = BeautifulSoup(src, "html.parser")
profiles = soup.find_all(class_="main-member-menu-profile")
print(f"Found {len(profiles)} member cards on page", flush=True)

# Quick parse: get name, guid, pid, level_code, pay_status, pay_date without modal click
members_basic = []
for prof in profiles:
    h6 = prof.find("h6")
    name = h6.get_text(strip=True) if h6 else ""
    if not name:
        continue
    level_p = prof.find("p", style=lambda s: s and "14px" in s)
    level_code = level_p.get_text(strip=True) if level_p else ""
    pathways_ps = prof.find_all("p")
    pathways_status = next((p.get_text(strip=True) for p in pathways_ps if "Pathways" in p.get_text()), "")
    footer = prof.find(class_="main-member-menu-box-footer")
    right  = footer.find(class_="main-member-menu-box-footer-riight") if footer else None
    a_tag  = right.find("a") if right else None
    p_tag  = right.find("p") if right else None
    pay_status = a_tag.get_text(strip=True) if a_tag else ""
    pay_date   = p_tag.get_text(strip=True) if p_tag else ""
    guid, pid = "", ""
    for a in prof.find_all("a", onclick=True):
        m = re.search(r"showModal\('([^']+)','([^']+)'\)", a["onclick"])
        if m:
            guid, pid = m.group(1), m.group(2)
            break
    if guid:
        members_basic.append({
            "name": name, "guid": guid, "pid": pid,
            "level_code": level_code, "pathways_status": pathways_status,
            "pay_status": pay_status, "pay_date": pay_date,
        })

print(f"Parsed {len(members_basic)} members with GUIDs", flush=True)

# ── Click each modal to get member_since ──────────────────────────────────────
print("\n── Fetching member_since via modals ─────────────────────────────────", flush=True)
all_members = []
for i, mem in enumerate(members_basic):
    name = mem["name"]
    guid = mem["guid"]
    print(f"  [{i+1}/{len(members_basic)}] {name}", end=" ", flush=True)
    modal_text   = ""
    member_since = ""
    try:
        link = driver.find_element(By.CSS_SELECTOR, f"a[onclick*='{guid}']")
        driver.execute_script("arguments[0].click();", link)
        time.sleep(4)
        # Try multiple selectors for the modal body
        modal_text = ""
        for sel in ["#information", ".modal-body", ".member-modal-body", "[class*='modal'] [class*='body']"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                raw = el.get_attribute("innerText") or ""
                if len(raw.strip()) > 30:
                    modal_text = re.sub(r'\s+', ' ', raw).strip()
                    break
            except Exception:
                continue
        since_m = re.search(r'Member since\s+([\w]+ \d+, \d{4})', modal_text)
        member_since = since_m.group(1) if since_m else ""
        print(f"→ since {member_since or '?'}", flush=True)
        force_close_modal(driver)
        time.sleep(1)
    except Exception as e:
        print(f"→ ERROR: {e}", flush=True)
        force_close_modal(driver)

    # Apply overrides from member_overrides.json
    mentor        = overrides.get("mentors", {}).get(name)
    new_members   = overrides.get("new_members", {})
    is_new_member = name in new_members
    # Override member_since if provided in overrides (e.g. for new members not yet in portal)
    if not member_since and name in new_members:
        member_since = new_members[name].get("joined", "")

    all_members.append({
        **mem,
        "modal_text":    modal_text,
        "member_since":  member_since,
        "mentor":        mentor,
        "is_new_member": is_new_member,
    })

modals_out = os.path.join(SCRIPT_DIR, "member_modals.json")
with open(modals_out, "w", encoding="utf-8") as f:
    json.dump(all_members, f, indent=2, ensure_ascii=False)
print(f"\nSaved {len(all_members)} members → {modals_out}", flush=True)

# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — Fetch Base Camp completions
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Fetching Base Camp completions ───────────────────────────────────", flush=True)
driver.get("https://www.toastmasters.org/myhome/go-to-base-camp")
time.sleep(15)

# Build authenticated requests session from browser cookies
sess = requests.Session()
ua   = driver.execute_script("return navigator.userAgent")
for c in driver.get_cookies():
    sess.cookies.set(c["name"], c["value"])
sess.headers.update({
    "User-Agent": ua, "Accept": "application/json",
    "Referer":    "https://basecamp.toastmasters.org/",
    "Origin":     "https://basecamp.toastmasters.org",
    "X-Requested-With": "XMLHttpRequest",
})
try:
    csrf = sess.get("https://basecamp.toastmasters.org/csrf/api/v1/token",
                    timeout=15).json().get("csrfToken", "")
    if csrf:
        sess.headers["X-CSRFToken"] = csrf
except Exception:
    pass

driver.quit()
print("Browser closed. Fetching via API...", flush=True)

BC = "https://basecamp.toastmasters.org"

def parse_outline(data):
    blocks = (data.get("course_blocks") or {}).get("blocks") or {}
    completion, resume_block = {}, None
    for bid, b in blocks.items():
        if b.get("type") == "sequential":
            name = b.get("display_name", "")
            if not name:
                continue
            done = bool(b.get("complete", False))
            completion[name] = done
            if b.get("resume_block") and not done:
                resume_block = name
    return completion, resume_block

results    = {}
ok_count   = 0
skip_count = 0

for m in sorted(all_members, key=lambda x: x["name"]):
    name = m["name"]
    guid = m.get("guid", "")
    if not guid:
        print(f"  [{name}] no GUID — skip", flush=True)
        skip_count += 1
        continue

    r = sess.get(f"{BC}/active_enrolled_courses?username={guid}", timeout=15)
    if r.status_code != 200 or not r.json():
        print(f"  [{name}] no active course — skip", flush=True)
        skip_count += 1
        continue

    course    = r.json()[0]["course"]
    course_id = course["id"]
    course_nm = course["name"]

    r2 = sess.get(f"{BC}/api/course_home/v1/outline/{course_id}/",
                  params={"username": guid}, timeout=30)
    if r2.status_code != 200:
        print(f"  [{name}] outline HTTP {r2.status_code} — skip", flush=True)
        skip_count += 1
        continue

    try:
        completion, resume = parse_outline(r2.json())
    except Exception as e:
        print(f"  [{name}] parse error: {e} — skip", flush=True)
        skip_count += 1
        continue

    done_list = [p for p, v in completion.items() if v]
    results[name] = {
        "pathway":     course_nm,
        "course_id":   course_id,
        "completion":  completion,
        "resume_next": resume,
    }
    ok_count += 1
    print(f"  {name} ({course_nm}): {len(done_list)} done", flush=True)

courses_out = os.path.join(SCRIPT_DIR, "member_courses.json")
with open(courses_out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nDone: {ok_count} fetched, {skip_count} skipped", flush=True)
print(f"Saved → {courses_out}", flush=True)


from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def make_driver():
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def build_session(driver):
    sess = requests.Session()
    ua = driver.execute_script("return navigator.userAgent")
    for c in driver.get_cookies():
        sess.cookies.set(c["name"], c["value"])
    sess.headers.update({
        "User-Agent": ua, "Accept": "application/json",
        "Referer": "https://basecamp.toastmasters.org/",
        "Origin": "https://basecamp.toastmasters.org",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        csrf = sess.get("https://basecamp.toastmasters.org/csrf/api/v1/token",
                        timeout=15).json().get("csrfToken", "")
        if csrf:
            sess.headers["X-CSRFToken"] = csrf
    except Exception:
        pass
    return sess

def parse_outline(data):
    blocks = (data.get("course_blocks") or {}).get("blocks") or {}
    completion = {}
    resume_block = None
    for bid, b in blocks.items():
        if b.get("type") == "sequential":
            name = b.get("display_name", "")
            if not name:
                continue
            complete = bool(b.get("complete", False))
            is_resume = bool(b.get("resume_block", False))
            completion[name] = complete
            if is_resume and not complete:
                resume_block = name
    return completion, resume_block

# ── Credentials from env vars ────────────────────────────────────────────────
email = os.environ.get("TM_EMAIL", "").strip()
password = os.environ.get("TM_PASSWORD", "").strip()
if not email or not password:
    raise SystemExit("ERROR: TM_EMAIL and TM_PASSWORD environment variables must be set.")

# ── Member list ───────────────────────────────────────────────────────────────
modals_path = os.path.join(SCRIPT_DIR, "member_modals.json")
with open(modals_path, encoding="utf-8") as f:
    all_members = json.load(f)

print("Logging in...", flush=True)
driver = make_driver()
wait = WebDriverWait(driver, 30)

driver.get("https://www.toastmasters.org/myhome")
time.sleep(5)
wait.until(EC.presence_of_element_located((By.ID, "signInName"))).send_keys(email)
driver.find_element(By.ID, "password").send_keys(password)
driver.find_element(By.ID, "continue").click()
time.sleep(10)
driver.get("https://www.toastmasters.org/myhome/go-to-base-camp")
time.sleep(15)

sess = build_session(driver)
BC = "https://basecamp.toastmasters.org"

print(f"\nFetching completions for {len(all_members)} members...\n", flush=True)

results = {}
ok_count = 0
skip_count = 0

for m in sorted(all_members, key=lambda x: x["name"]):
    name = m["name"]
    guid = m.get("guid", "")
    if not guid:
        print(f"  [{name}] no GUID — skip", flush=True)
        skip_count += 1
        continue

    r = sess.get(f"{BC}/active_enrolled_courses?username={guid}", timeout=15)
    if r.status_code != 200 or not r.json():
        print(f"  [{name}] no active course — skip", flush=True)
        skip_count += 1
        continue

    course = r.json()[0]["course"]
    course_id = course["id"]
    course_name = course["name"]

    r2 = sess.get(f"{BC}/api/course_home/v1/outline/{course_id}/",
                  params={"username": guid}, timeout=30)

    if r2.status_code != 200:
        print(f"  [{name}] outline {r2.status_code} — skip", flush=True)
        skip_count += 1
        continue

    try:
        completion, resume = parse_outline(r2.json())
    except Exception as e:
        print(f"  [{name}] parse error: {e} — skip", flush=True)
        skip_count += 1
        continue

    done = [p for p, v in completion.items() if v]
    results[name] = {
        "pathway": course_name,
        "course_id": course_id,
        "completion": completion,
        "resume_next": resume,
    }
    ok_count += 1
    print(f"  {name} ({course_name}): {len(done)} done", flush=True)

driver.quit()

out_path = os.path.join(SCRIPT_DIR, "member_courses.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nDone: {ok_count} fetched, {skip_count} skipped", flush=True)
print(f"Saved to {out_path}", flush=True)
