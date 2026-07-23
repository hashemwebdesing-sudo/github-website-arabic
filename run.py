#!/usr/bin/env python3
"""يشغّل الخطوات الثلاث بالتسلسل: جلب → حُكم/شرح → بناء الموقع.

هذا هو الأمر الوحيد الذي تستدعيه المهمة المجدولة (cron) على Hostinger:
    python3 run.py

المتغيرات البيئية المستخدمة:
    GROQ_API_KEY   (مطلوب للحُكم والشرح)
    GITHUB_TOKEN   (اختياري — يرفع حد طلبات GitHub؛ يعمل بدونه)
    SITE_DIR       (مجلد إخراج الموقع، مثل مجلد public_html للسب دومين)
    SITE_URL       (رابط الموقع النهائي، مثل https://radar.example.com/)
"""

import os
import subprocess
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
STEPS = ["fetch_repos.py", "summarize.py", "build_site.py"]


def load_config():
    """يقرأ config.env (أسطر KEY=VALUE) ويضبط متغيرات البيئة إن لم تكن مضبوطة.

    يسهّل الإعداد على الاستضافة المشتركة: تعبّي config.env والمهمة المجدولة
    تشغّل فقط: python3 run.py
    """
    cfg = ROOT / "config.env"
    if not cfg.exists():
        return
    for raw in cfg.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def main():
    load_config()
    for name in STEPS:
        print(f"\n=== {name} ===", flush=True)
        result = subprocess.run([sys.executable, str(SCRIPTS / name)])
        if result.returncode != 0:
            # لا نوقف السلسلة: لو فشل الجلب مثلاً، نبني الموقع من البيانات الحالية
            print(f"تحذير: {name} انتهى برمز {result.returncode}", file=sys.stderr)
    print("\nتم.", flush=True)


if __name__ == "__main__":
    main()
