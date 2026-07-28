"""يجلب أقوى 15 مستودع على GitHub عموماً (الأكثر نجوماً) ويحفظها في data/top.json.

قائمة العمالقة تتغيّر ببطء شديد، لذا يكفي تحديثها مرة كل 12 ساعة.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from httputil import get_json

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
TOP_FILE = ROOT / "data" / "top.json"
TOP_N = 15
REFRESH_HOURS = 12


def is_fresh():
    """هل الملف حديث بما يكفي؟ (لتقليل الطلبات على GitHub)"""
    if not TOP_FILE.exists():
        return False
    try:
        data = json.loads(TOP_FILE.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(data["fetched_at"])
        age_h = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600
        return age_h < REFRESH_HOURS and len(data.get("items", [])) >= TOP_N
    except Exception:
        return False


def main():
    if is_fresh():
        print("قائمة الأقوى حديثة — لا حاجة للتحديث.")
        return

    status, data = get_json(
        "https://api.github.com/search/repositories",
        params={"q": "stars:>100000", "sort": "stars", "order": "desc", "per_page": TOP_N},
    )
    if status != 200 or not data:
        print(f"تعذّر جلب قائمة الأقوى ({status}).", file=sys.stderr)
        return

    items = [
        {
            "full_name": r["full_name"],
            "html_url": r["html_url"],
            "stars": r["stargazers_count"],
            "language": r.get("language") or "",
            "description": r.get("description") or "",
        }
        for r in data.get("items", [])[:TOP_N]
    ]

    TOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOP_FILE.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "items": items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"تم جلب أقوى {len(items)} مستودع على GitHub.")


if __name__ == "__main__":
    main()
