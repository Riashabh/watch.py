"""Ping your phone when new rows appear in speedyapply's NEW_GRAD_USA.md."""
import os
import re
import sys
import urllib.request

SRC = "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md"
SEEN_FILE = "seen.txt"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
# Optional: comma-separated, case-insensitive. Empty = notify on everything.
KEYWORDS = [k.strip().lower() for k in os.environ.get("KEYWORDS", "").split(",") if k.strip()]
MAX_SINGLE = 8  # above this, send one digest instead of N pushes

HREF = re.compile(r'href="([^"]+)"')
TAG = re.compile(r"<[^>]+>")


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def parse(md):
    jobs, section = [], "Other"
    for line in md.splitlines():
        if line.startswith("### "):
            section = line[4:].split(":")[0].strip()
        if not line.startswith("| <a"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        apply_cell = next((c for c in cells if 'alt="Apply"' in c), None)
        if not apply_cell:
            continue
        has_salary = len(cells) == 6
        jobs.append({
            "id": HREF.search(apply_cell).group(1),
            "company": TAG.sub("", cells[0]).strip(),
            "role": cells[1],
            "location": cells[2],
            "salary": cells[3] if has_salary else "",
            "section": section,
        })
    return jobs


def wanted(job):
    if not KEYWORDS:
        return True
    text = f"{job['company']} {job['role']} {job['location']}".lower()
    return any(k in text for k in KEYWORDS)


def push(title, body, click=None):
    if not NTFY_TOPIC:
        print(f"[dry run] {title}\n{body}\n")
        return
    headers = {"Title": title.encode("utf-8"), "Tags": "briefcase"}
    if click:
        headers["Click"] = click
    req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}", data=body.encode("utf-8"), headers=headers)
    urllib.request.urlopen(req, timeout=30)


def main():
    jobs = parse(fetch(SRC))
    if len(jobs) < 50:  # upstream format changed or bad fetch; don't wipe state
        sys.exit(f"Only parsed {len(jobs)} jobs, refusing to continue")

    first_run = not os.path.exists(SEEN_FILE)
    seen = set() if first_run else set(open(SEEN_FILE).read().split())
    new = [j for j in jobs if j["id"] not in seen]

    with open(SEEN_FILE, "w") as f:
        f.write("\n".join(sorted(seen | {j["id"] for j in jobs})) + "\n")

    if first_run:
        print(f"Seeded {len(jobs)} jobs, no notifications sent")
        return

    hits = [j for j in new if wanted(j)]
    print(f"{len(new)} new, {len(hits)} match filters")

    if len(hits) > MAX_SINGLE:
        lines = [f"{j['company']}: {j['role']} ({j['location']})" for j in hits]
        push(f"{len(hits)} new grad jobs", "\n".join(lines),
             "https://github.com/speedyapply/2027-SWE-College-Jobs/blob/main/NEW_GRAD_USA.md")
        return
    for j in hits:
        extra = f" | {j['salary']}" if j["salary"] else ""
        push(f"{j['company']} [{j['section']}]", f"{j['role']}\n{j['location']}{extra}", j["id"])


if __name__ == "__main__":
    main()
