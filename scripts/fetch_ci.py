"""
CI version of fetch_all_completions.py
- Uses Chrome (works on GitHub Actions Ubuntu runners)
- Reads credentials from TM_EMAIL / TM_PASSWORD env vars
- Reads member_modals.json from same directory (written from MEMBER_MODALS_JSON secret)
- Writes member_courses.json to same directory
"""
import os, sys, time, json, requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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
