"""يجلب المستودعات الجديدة المميزة من GitHub ويحفظ الجديد منها في data/repos.json.

جديد ومطلوب = أُنشئ خلال آخر 14 يوم ووصل 200 نجمة فأكثر.
"""

import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality import is_junk_text
from httputil import get_json

# ضمان طباعة العربية بشكل صحيح على أي نظام (خاصة ويندوز)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"

MIN_STARS = 200
DAYS_BACK = 21
MAX_RESULTS = 50          # نجلب عدداً أكبر لأن الفلترة تستبعد جزءاً
README_MAX_CHARS = 8000
README_MIN_CHARS = 200    # README أقصر من هذا غالباً مشروع فارغ/ريسكِن

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
    status, data = get_json(
        f"{GITHUB_API}/search/repositories",
        headers=_headers(),
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": MAX_RESULTS,
        },
    )
    if status != 200:
        raise RuntimeError(f"GitHub search رجّع {status}: {str(data)[:200]}")
    return (data or {}).get("items", [])


def fetch_readme(full_name):
    status, data = get_json(f"{GITHUB_API}/repos/{full_name}/readme", headers=_headers())
    if status != 200 or not data:
        return ""
    try:
        text = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
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
    skipped = 0
    for item in items:
        full_name = item["full_name"]
        if full_name in known:
            continue

        description = item.get("description") or ""
        topics = item.get("topics") or []

        # الطبقة الأولى: فلتر قواعد سريع (قبل جلب README لتوفير الطلبات)
        if item.get("fork"):
            skipped += 1
            continue
        if not description.strip():
            skipped += 1
            continue
        if is_junk_text(item["name"], description, topics):
            print(f"  - مستبعَد (فئة مزعجة): {full_name}")
            skipped += 1
            continue

        readme = fetch_readme(full_name)
        if len(readme.strip()) < README_MIN_CHARS:
            print(f"  - مستبعَد (README ضعيف): {full_name}")
            skipped += 1
            continue

        print(f"  + مرشّح: {full_name} ({item['stargazers_count']}⭐)")
        record = {
            "full_name": full_name,
            "name": item["name"],
            "owner": item["owner"]["login"],
            "html_url": item["html_url"],
            "description": description,
            "language": item.get("language") or "",
            "topics": topics,
            "stars": item["stargazers_count"],
            "created_at": item["created_at"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "readme": readme,
            "verdict": None,     # يملأه الحَكَم في summarize.py
            "summary_ar": None,
            "summary_en": None,
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
    print(f"تمت الإضافة: {added} مرشّح جديد (استُبعد {skipped}). الإجمالي: {len(archive)}.")
    return added


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"خطأ في جلب المستودعات: {e}", file=sys.stderr)
        sys.exit(1)
