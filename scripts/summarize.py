"""يولّد شرحاً عربياً لكل مستودع لم يُشرَح بعد، عبر Claude API (Haiku 4.5).

يقرأ data/repos.json، ويملأ الحقل summary_ar للمستودعات التي قيمته فيها None،
ثم يحفظ. فشل مستودع واحد لا يوقف الباقي، ولا يُعاد شرح ما تم شرحه (لتوفير التكلفة).
"""

import json
import os
import sys
import time
from pathlib import Path

import anthropic

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1500
MAX_RETRIES = 3

# حد أقصى اختياري لعدد المستودعات المشروحة في كل تشغيل (لضبط التكلفة).
# 0 = بلا حد. يُضبط عبر متغير البيئة SUMMARIZE_LIMIT.
LIMIT = int(os.environ.get("SUMMARIZE_LIMIT", "0"))

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "what": {"type": "string", "description": "شو المشروع، سطرين بلغة بسيطة"},
        "why": {"type": "string", "description": "ليش مميز وليش الناس متحمسة له"},
        "who": {"type": "string", "description": "مين يستفيد منه"},
        "try": {"type": "string", "description": "كيف تجرّبه، أوامر التثبيت الأساسية"},
    },
    "required": ["what", "why", "who", "try"],
    "additionalProperties": False,
}

PROMPT_TEMPLATE = """أنت خبير تقني تشرح مشاريع GitHub لشخص عربي مبتدئ ضعيف بالإنجليزي ويحب التقنية.
اشرح المستودع التالي بالعربي الفصيح البسيط والواضح. لا تستخدم مصطلحات إنجليزية معقّدة دون توضيحها.

اسم المستودع: {full_name}
اللغة: {language}
الوصف الرسمي: {description}
عدد النجوم: {stars}

مقتطف من ملف README:
---
{readme}
---

أعطني الشرح مقسّماً إلى:
- what: شو هو هذا المشروع؟ (جملتين، بلغة بسيطة جداً)
- why: ليش مميز وليش الناس متحمسة له ووصل لهذا العدد من النجوم بسرعة؟
- who: مين الأشخاص اللي بيستفيدوا منه؟
- try: كيف يقدر الواحد يجرّبه؟ (خطوات أو أوامر تثبيت مختصرة)
"""


def load_repos():
    if not DATA_FILE.exists():
        print("لا يوجد data/repos.json — شغّل fetch_repos.py أولاً.", file=sys.stderr)
        sys.exit(1)
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_repos(repos):
    DATA_FILE.write_text(
        json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def summarize_one(client, repo):
    prompt = PROMPT_TEMPLATE.format(
        full_name=repo["full_name"],
        language=repo["language"] or "غير محدد",
        description=repo["description"] or "لا يوجد وصف",
        stars=repo["stars"],
        readme=repo["readme"] or "لا يوجد README",
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
                output_config={
                    "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}
                },
            )
            text = next(b.text for b in response.content if b.type == "text")
            return json.loads(text)
        except anthropic.RateLimitError as e:
            wait = 2 ** attempt
            print(f"    تجاوز الحد، انتظار {wait} ثانية... ({e})", file=sys.stderr)
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            print(f"    خطأ API ({e.status_code})، محاولة {attempt}/{MAX_RETRIES}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return None


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("متغير البيئة ANTHROPIC_API_KEY غير موجود.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()
    repos = load_repos()

    pending = [r for r in repos if r.get("summary_ar") is None]
    if LIMIT > 0:
        pending = pending[:LIMIT]

    print(f"مستودعات بحاجة لشرح: {len(pending)}")

    done = 0
    for repo in pending:
        print(f"  شرح: {repo['full_name']} ...")
        summary = summarize_one(client, repo)
        if summary:
            repo["summary_ar"] = summary
            done += 1
            save_repos(repos)  # حفظ تدريجي حتى لا نخسر ما تم عند أي انقطاع
        else:
            print(f"    فشل شرح {repo['full_name']}، سيُعاد لاحقاً.", file=sys.stderr)

    print(f"تم شرح {done} مستودع.")


if __name__ == "__main__":
    main()
