# Generate website/data.js from scraped Toastmasters member data.
# Run from: the scripts folder inside website/
#
import json, os
from datetime import datetime
import os as _os_path
SCRIPT_DIR = _os_path.path.dirname(_os_path.path.abspath(__file__))

# ── LOAD member_overrides.json ────────────────────────────────────────────────
_overrides_file = _os_path.path.join(SCRIPT_DIR, "member_overrides.json")
_overrides = {}
if os.path.exists(_overrides_file):
    with open(_overrides_file, encoding="utf-8") as _of:
        _overrides = json.load(_of)
    print(f"Loaded member_overrides.json")

# ── MANUAL PROJECT COMPLETION OVERRIDES ─────────────────────────────────────
# Loaded from member_overrides.json["manual_completions"] — edit that file.
# These ALWAYS win over API data.
# ────────────────────────────────────────────────────────────────────────────
MANUAL_PROJECT_COMPLETION = {}
for _name, _projs in _overrides.get("manual_completions", {}).items():
    MANUAL_PROJECT_COMPLETION[_name] = dict(_projs)
print(f"Manual completions loaded for {len(MANUAL_PROJECT_COMPLETION)} members: {list(MANUAL_PROJECT_COMPLETION.keys())}")

# ── AUTO-MERGE: member_courses.json (from fetch_ci.py) ──────────────────────
# Manual overrides take precedence over API data.
_courses_file = _os_path.path.join(SCRIPT_DIR, "member_courses.json")
if os.path.exists(_courses_file):
    try:
        with open(_courses_file, encoding="utf-8") as _f:
            _courses_data = json.load(_f)
        with open(_os_path.path.join(SCRIPT_DIR, "member_modals.json"), encoding="utf-8") as _mf:
            _pay_status_map = {m["name"]: m.get("pay_status", "") for m in json.load(_mf)}
        _api_merged = 0
        for _name, _info in _courses_data.items():
            if _pay_status_map.get(_name) == "Membership Pending":
                continue
            _api_completion = {p: v for p, v in _info.get("completion", {}).items() if v}
            if _api_completion:
                if _name not in MANUAL_PROJECT_COMPLETION:
                    MANUAL_PROJECT_COMPLETION[_name] = {}
                for _proj, _done in _api_completion.items():
                    if _proj not in MANUAL_PROJECT_COMPLETION[_name]:
                        MANUAL_PROJECT_COMPLETION[_name][_proj] = _done
                        _api_merged += 1
        print(f"Merged API data from member_courses.json ({_api_merged} additions, manual overrides preserved)")
    except Exception as _e:
        print(f"Could not merge member_courses.json: {_e}")
else:
    print("No member_courses.json found")

with open(_os_path.path.join(SCRIPT_DIR, "member_modals.json"), encoding="utf-8") as f:
    all_members = json.load(f)

EXCOM_INFO = {
    "Lakshmi Satya Sai Sindhu Karri":  {"role": "Club President",       "pathway": "Presentation Mastery", "completed_levels": 0},
    "Mahabir Singh Bisht":             {"role": "Club Secretary",        "pathway": "Presentation Mastery", "completed_levels": 0},
    "Nemichandra B N":                 {"role": "VP Membership",         "pathway": "Dynamic Leadership",   "completed_levels": 0},
    "Sahil Aggarwal":                  {"role": "Club Treasurer",        "pathway": None,                   "completed_levels": -1},
    "Sheetal Avula":                   {"role": "VP Education",          "pathway": "Presentation Mastery", "completed_levels": 0},
    "Yamuna J K":                      {"role": "VP PR",                 "pathway": "Presentation Mastery", "completed_levels": 0},
}

LEVEL_ABBR = {
    "LD": "Leadership Development", "EC": "Effective Coaching",
    "TC": "Team Collaboration",     "IP": "Innovative Planning",
    "DL": "Dynamic Leadership",     "PM": "Presentation Mastery",
    "EH": "Engaging Humor",         "MS": "Motivational Strategies",
    "PI": "Persuasive Influence",
}

PATHWAY_COLORS = {
    "Presentation Mastery":  "#7c3aed",
    "Effective Coaching":    "#2563eb",
    "Dynamic Leadership":    "#dc2626",
    "Team Collaboration":    "#0891b2",
    "Engaging Humor":        "#ea580c",
    "Innovative Planning":   "#16a34a",
    "Leadership Development":"#b45309",
    "Motivational Strategies":"#7c3aed",
    "Persuasive Influence":  "#be185d",
}

PATHWAY_PROJECTS = {
    "Presentation Mastery": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Writing a Speech with Purpose","Introduction to Vocal Variety and Body Language","Evaluation and Feedback"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Understanding Your Communication Style","Effective Body Language","Introduction to Toastmasters Mentoring"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Persuasive Speaking"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["Managing a Difficult Audience"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Prepare to Speak Professionally"], "elective_count": 1},
    },
    "Effective Coaching": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Evaluation and Feedback","Researching and Presenting"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Understanding Your Leadership Style","Understanding Your Communication Style","Introduction to Toastmasters Mentoring"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Successful Collaboration"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["Motivate Others"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Lead in Any Situation","Reflect on Your Path"], "elective_count": 1},
    },
    "Team Collaboration": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Writing a Speech with Purpose","Introduction to Vocal Variety and Body Language","Evaluation and Feedback"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Understanding Your Leadership Style","Introduction to Toastmasters Mentoring"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Successful Collaboration"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["Motivate Others"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Lead in Any Situation"], "elective_count": 1},
    },
    "Dynamic Leadership": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Writing a Speech with Purpose","Introduction to Vocal Variety and Body Language","Evaluation and Feedback","Researching and Presenting"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Understanding Your Leadership Style","Understanding Your Communication Style","Introduction to Toastmasters Mentoring"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Negotiate the Best Outcome"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["Manage Change"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Lead in Any Situation"], "elective_count": 1},
    },
    "Leadership Development": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Evaluation and Feedback","Researching and Presenting"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Understanding Your Leadership Style","Introduction to Toastmasters Mentoring"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Planning and Implementing"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["Leading Your Team"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Lead in Any Situation"], "elective_count": 1},
    },
    "Innovative Planning": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Evaluation and Feedback","Researching and Presenting"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Understanding Your Leadership Style","Connect with Your Audience"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Present a Proposal"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["Manage a Difficult Audience"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Lead in Any Situation"], "elective_count": 1},
    },
    "Engaging Humor": {
        1: {"title": "Mastering Fundamentals",    "required": ["Ice Breaker","Writing a Speech with Purpose","Introduction to Vocal Variety and Body Language","Evaluation and Feedback","Researching and Presenting"], "elective_count": 0},
        2: {"title": "Learning Your Style",       "required": ["Know Your Sense of Humor","Connect with Your Audience","Introduction to Toastmasters Mentoring"], "elective_count": 0},
        3: {"title": "Increasing Knowledge",      "required": ["Engage Your Audience With Humor"], "elective_count": 1},
        4: {"title": "Building Skills",           "required": ["The Power of Humor in an Impromptu Speech"], "elective_count": 1},
        5: {"title": "Demonstrating Expertise",   "required": ["Deliver Your Message with Humor"], "elective_count": 1},
    },
}

def decode_level_code(code):
    if not code:
        return None, None
    code = code.strip()
    if code == "DTM":
        return "Distinguished Toastmaster", 99
    for abbr in sorted(LEVEL_ABBR.keys(), key=len, reverse=True):
        if code.upper().startswith(abbr):
            rest = code[len(abbr):]
            if rest.isdigit():
                return LEVEL_ABBR[abbr], int(rest)
    return None, None

def build_levels(pathway, completed_levels):
    if not pathway or pathway not in PATHWAY_PROJECTS:
        return []
    levels = []
    for lvl_num in range(1, 6):
        info = PATHWAY_PROJECTS[pathway][lvl_num]
        if completed_levels == 99:
            status = "complete"
        elif lvl_num <= completed_levels:
            status = "complete"
        elif lvl_num == completed_levels + 1:
            status = "current"
        else:
            status = "future"
        projects = list(info["required"])
        if info["elective_count"] > 0:
            projects.append(f"+ {info['elective_count']} Elective project (your choice)")
        projects.append(f"Level {lvl_num} Completion")
        levels.append({
            "level": lvl_num,
            "title": info["title"],
            "status": status,
            "projects": projects,
        })
    return levels

def pay_status_key(m):
    s = m.get("pay_status", "")
    if s == "Paid Until":
        return 0
    if s == "Membership Pending":
        return 1
    return 2

# Active course overrides (TC5/DL5 complete → new pathway)
ACTIVE_COURSE_OVERRIDES = {
    "Akash Yadav":  ("Engaging Humor", 0),
    "Roopa V. G":   ("Engaging Humor", 4),  # Education awards show EH4
}

club_data_members = []
membership_data = []

for m in sorted(all_members, key=lambda x: x.get("name", "")):
    name     = m["name"]
    level_code = m.get("level_code", "").strip()
    pay_status = m.get("pay_status", "")
    pay_date   = m.get("pay_date", "")
    member_since = m.get("member_since", "")
    pid        = m.get("pid", "")
    mentor     = m.get("mentor", None)
    is_new_member = m.get("is_new_member", False)

    # Determine pathway + completed levels
    if name in EXCOM_INFO:
        ex = EXCOM_INFO[name]
        pathway = ex["pathway"]
        completed = ex["completed_levels"]
        role = ex["role"]
    else:
        role = ""
        if name in ACTIVE_COURSE_OVERRIDES:
            pathway, completed = ACTIVE_COURSE_OVERRIDES[name]
        else:
            pathway, completed = decode_level_code(level_code)
            if pathway is None and m.get("pathways_status") == "Pathways Enrolled":
                pathway = "Enrolled (pathway TBD)"
                completed = 0

    # Pay status normalisation
    if pay_status == "Paid Until":
        pay_norm = "paid"
    elif pay_status == "Membership Pending":
        pay_norm = "pending"
    elif not pay_status:
        pay_norm = "unknown"
    else:
        pay_norm = "unpaid"

    is_dtm = (level_code == "DTM")
    not_enrolled = (pathway is None)

    levels = build_levels(pathway, completed if completed is not None else -1)

    club_data_members.append({
        "name":             name,
        "pathway":          pathway or ("DTM – All Complete" if is_dtm else None),
        "pathway_color":    PATHWAY_COLORS.get(pathway, "#6b7280"),
        "completed_levels": completed if (completed is not None and completed >= 0) else 0,
        "total_levels":     5,
        "is_dtm":           is_dtm,
        "not_enrolled":     not_enrolled and not is_dtm,
        "excom_role":       role or None,
        "pay_norm":         pay_norm,
        "mentor":           mentor,
        "member_since":     member_since,
        "is_new_member":    is_new_member,
        "levels":           levels,
    })

    membership_data.append({
        "name":         name,
        "pid":          pid,
        "member_since": member_since,
        "pay_status":   pay_status or "Unknown",
        "pay_date":     pay_date,
        "pay_norm":     pay_norm,
        "excom_role":   role or None,
        "pathway":      pathway or ("DTM" if is_dtm else "Not Enrolled"),
    })

# CI: output goes to repo root

pathway_structures_js = {}
for path, levels in PATHWAY_PROJECTS.items():
    pathway_structures_js[path] = {}
    for lvl, info in levels.items():
        pathway_structures_js[path][str(lvl)] = info

now_str = datetime.now().strftime('%d %b %Y, %H:%M')
club_json = json.dumps(
    {"club_name": "Narrator's Club", "generated_at": now_str, "members": club_data_members},
    indent=2, ensure_ascii=False
)
mem_sorted = sorted(membership_data, key=lambda x: (0 if x['pay_norm']=='unpaid' else 1 if x['pay_norm']=='pending' else 2, x['name']))
mem_json   = json.dumps(mem_sorted, indent=2, ensure_ascii=False)
ps_json    = json.dumps(pathway_structures_js, indent=2, ensure_ascii=False)
mpc_json   = json.dumps(MANUAL_PROJECT_COMPLETION, indent=2, ensure_ascii=False)

out = [
    "// Auto-generated by generate_website_data.py",
    f"// Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "",
    "window.EXCOM_PASSWORD = 'Narrators@2025';",
    "",
    f"window.CLUB_DATA = {club_json};",
    "",
    f"window.MEMBERSHIP_DATA = {mem_json};",
    "",
    f"window.PATHWAY_STRUCTURES = {ps_json};",
    "",
    f"window.PROJECT_COMPLETION_SEED = {mpc_json};",
]

with open(_os_path.path.join(SCRIPT_DIR, "..", "data.js"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print("Generated data.js successfully! (CI output to repo root)")
print(f"  {len(club_data_members)} members exported")
paid   = sum(1 for m in membership_data if m['pay_norm'] == 'paid')
unpaid = sum(1 for m in membership_data if m['pay_norm'] == 'unpaid')
pending= sum(1 for m in membership_data if m['pay_norm'] == 'pending')
print(f"  Paid: {paid}  |  Unpaid: {unpaid}  |  Pending: {pending}")

