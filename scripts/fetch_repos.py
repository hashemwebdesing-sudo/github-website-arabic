"""يجلب المستودعات الجديدة المميزة من GitHub ويحفظ الجديد منها في data/repos.json.

جديد ومطلوب = أُنشئ خلال آخر 14 يوم ووصل 200 نجمة فأكثر.
"""

import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ضمان طباعة العربية بشكل صحيح على أي نظام (خاصة ويندوز)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"

MIN_STARS = 200
DAYS_BACK = 14
MAX_RESULTS = 30
README_MAX_CHARS = 8000

GITHUB_API = "https://api.github.com"


def _headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def load_archive():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def save_archive(repos):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def search_trending():
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    query = f"created:>{since} stars:>={MIN_STARS}"
    resp = requests.get(
        f"{GITHUB_API}/search/repositories",
        headers=_headers(),
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": MAX_RESULTS,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def fetch_readme(full_name):
    resp = requests.get(
        f"{GITHUB_API}/repos/{full_name}/readme",
        headers=_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        return ""
    content = resp.json().get("content", "")
    try:
        text = base64.b64decode(content).decode("utf-8", errors="replace")
    except Exception:
        return ""
    return text[:README_MAX_CHARS]


def main():
    archive = load_archive()
    known = {r["full_name"] for r in archive}

    print(f"جاري البحث عن مستودعات جديدة (>= {MIN_STARS} نجمة، آخر {DAYS_BACK} يوم)...")
    items = search_trending()
    print(f"رجّع GitHub {len(items)} مستودع.")

    added = 0
    for item in items:
        full_name = item["full_name"]
        if full_name in known:
            continue

        print(f"  + جديد: {full_name} ({item['stargazers_count']}⭐)")
        readme = fetch_readme(full_name)

        record = {
            "full_name": full_name,
            "name": item["name"],
            "owner": item["owner"]["login"],
            "html_url": item["html_url"],
            "description": item.get("description") or "",
            "language": item.get("language") or "",
            "stars": item["stargazers_count"],
            "created_at": item["created_at"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "readme": readme,
            "summary_ar": None,  # يملأه summarize.py لاحقاً
        }
        archive.append(record)
        known.add(full_name)
        added += 1

    # تحديث عدد النجوم للمستودعات القديمة الموجودة أصلاً
    stars_now = {i["full_name"]: i["stargazers_count"] for i in items}
    for r in archive:
        if r["full_name"] in stars_now:
            r["stars"] = stars_now[r["full_name"]]

    save_archive(archive)
    print(f"تمت الإضافة: {added} مستودع جديد. الإجمالي في الأرشيف: {len(archive)}.")
    return added


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"خطأ من GitHub API: {e}", file=sys.stderr)
        sys.exit(1)
