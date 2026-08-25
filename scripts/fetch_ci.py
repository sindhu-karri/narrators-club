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
# PART 2 — Fetch BCM Progress API (all members, all paths, all levels)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Fetching BCM progress data ───────────────────────────────────────", flush=True)
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
})
try:
    csrf = sess.get("https://basecamp.toastmasters.org/csrf/api/v1/token",
                    timeout=15).json().get("csrfToken", "")
    if csrf:
        sess.headers["X-CSRFToken"] = csrf
except Exception:
    pass

# Get club UUID from roles API
club_uuid = None
try:
    roles = sess.get("https://basecamp.toastmasters.org/api/members/roles", timeout=15).json()
    if roles:
        club_uuid = roles[0]["uuid"]
        print(f"Club UUID: {club_uuid}", flush=True)
except Exception as e:
    print(f"Could not get club UUID: {e}", flush=True)

driver.quit()
print("Browser closed.", flush=True)

if not club_uuid:
    print("ERROR: no club UUID — cannot fetch BCM progress", flush=True)
else:
    # Fetch all pages
    all_progress = []
    page = 1
    while True:
        url = f"https://basecamp.toastmasters.org/api/bcm/progress/?club={club_uuid}&page={page}"
        r = sess.get(url, timeout=20)
        if r.status_code != 200:
            print(f"  Page {page}: HTTP {r.status_code} — stopping", flush=True)
            break
        data = r.json()
        results_page = data.get("results", [])
        all_progress.extend(results_page)
        print(f"  Page {page}: {len(results_page)} records", flush=True)
        if not data.get("next"):
            break
        page += 1

    print(f"Total BCM records: {len(all_progress)}", flush=True)

    # Build member_courses.json — keep best path per member (most approved levels)
    # Also build name lookup: BCM name -> portal name (for fuzzy matching)
    portal_names = [m["name"] for m in all_members]

    def best_portal_name(bcm_name):
        # Exact match first
        if bcm_name in portal_names:
            return bcm_name
        # Last name match
        bcm_parts = bcm_name.lower().split()
        for pn in portal_names:
            pn_parts = pn.lower().split()
            if bcm_parts[-1] == pn_parts[-1] and bcm_parts[0] == pn_parts[0]:
                return pn
        # Partial: first + last
        for pn in portal_names:
            pn_lower = pn.lower()
            if bcm_parts[0] in pn_lower and bcm_parts[-1] in pn_lower:
                return pn
        return bcm_name  # fallback

    member_courses = {}
    for rec in all_progress:
        bcm_name = rec["user"]["name"]
        name     = best_portal_name(bcm_name)
        path     = rec["path_name"]
        prog     = rec["progression"]
        approved = sum(1 for v in prog.values() if isinstance(v, dict) and v.get("approved"))
        existing = member_courses.get(name, {})
        # Keep the path with more approved levels (their primary active path)
        if approved >= existing.get("completed_levels", -1):
            member_courses[name] = {
                "pathway":          path,
                "completed_levels": approved,
                "progression":      prog,
            }

    courses_out = os.path.join(SCRIPT_DIR, "member_courses.json")
    with open(courses_out, "w", encoding="utf-8") as f:
        json.dump(member_courses, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(member_courses)} members → {courses_out}", flush=True)
    for name, v in sorted(member_courses.items()):
        prog = v["progression"]
        cur  = next(((k, x) for k, x in prog.items()
                     if isinstance(x, dict) and not x.get("approved") and x.get("completed", 0) > 0), None)
        print(f"  {name} | {v['pathway']} | L_done={v['completed_levels']}", end="")
        if cur:
            print(f" | {cur[0]}: {cur[1]['completed']}/{cur[1]['total']}", end="")
        print(flush=True)

