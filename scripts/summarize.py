"""يولّد شرحاً عربياً لكل مستودع لم يُشرَح بعد، عبر Groq (نماذج Llama — سريعة ومجانية).

يقرأ data/repos.json، ويملأ الحقل summary_ar للمستودعات التي قيمته فيها None،
ثم يحفظ. فشل مستودع واحد لا يوقف الباقي، ولا يُعاد شرح ما تم شرحه.

يحتاج متغير البيئة GROQ_API_KEY (مفتاح مجاني من https://console.groq.com).
النموذج قابل للتغيير عبر GROQ_MODEL.
"""

import json
import os
import sys
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = 1500
MAX_RETRIES = 4

# حد أقصى اختياري لعدد المستودعات في كل تشغيل (SUMMARIZE_LIMIT). 0 = بلا حد.
LIMIT = int(os.environ.get("SUMMARIZE_LIMIT", "0"))

REQUIRED_KEYS = ("what", "why", "who", "try")

PROMPT_TEMPLATE = """أنت خبير تقني تشرح مشاريع GitHub لشخص عربي يحب التقنية لكنه ضعيف بالإنجليزي.
اشرح المستودع التالي بالعربي الفصيح البسيط والواضح، دون مصطلحات إنجليزية معقّدة إلا مع توضيحها.

اسم المستودع: {full_name}
اللغة: {language}
الوصف الرسمي: {description}
عدد النجوم: {stars}

مقتطف من ملف README:
---
{readme}
---

أعِد الإجابة **بصيغة JSON فقط** (بدون أي نص خارج الـ JSON)، بهذا الشكل تماماً:
{{
  "what": "شو هو هذا المشروع؟ جملتان بلغة بسيطة جداً",
  "why": "ليش مميز وليش الناس متحمسة له ووصل لهذا العدد من النجوم بسرعة",
  "who": "مين الأشخاص اللي بيستفيدوا منه",
  "try": "كيف يجرّبه الواحد؟ خطوات أو أوامر تثبيت مختصرة"
}}
كل القيم بالعربي. لا تضع أي شرح أو تعليق خارج الـ JSON."""


def load_repos():
    if not DATA_FILE.exists():
        print("لا يوجد data/repos.json — شغّل fetch_repos.py أولاً.", file=sys.stderr)
        sys.exit(1)
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def save_repos(repos):
    DATA_FILE.write_text(
        json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def valid_summary(obj):
    return isinstance(obj, dict) and all(
        isinstance(obj.get(k), str) and obj.get(k).strip() for k in REQUIRED_KEYS
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
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=0.4,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content
            data = json.loads(text)
            # بعض النماذج تلفّ الناتج داخل مفتاح واحد — نفكّه إن لزم
            if not valid_summary(data) and len(data) == 1:
                inner = next(iter(data.values()))
                if valid_summary(inner):
                    data = inner
            if valid_summary(data):
                return {k: data[k].strip() for k in REQUIRED_KEYS}
            print("    ناتج غير مكتمل، إعادة المحاولة...", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — نتعامل مع كل أخطاء الشبكة/الحد بنفس المنطق
            wait = min(2 ** attempt, 30)
            print(f"    خطأ ({type(e).__name__}): {e} — انتظار {wait}ث", file=sys.stderr)
            time.sleep(wait)
    return None


def main():
    repos = load_repos()
    pending = [r for r in repos if r.get("summary_ar") is None]
    if LIMIT > 0:
        pending = pending[:LIMIT]

    if not pending:
        print("لا يوجد مستودعات بحاجة لشرح.")
        return

    # نحتاج المفتاح فقط لو في مستودعات جديدة. غيابه لا يكسر النشر —
    # تبقى المستودعات "قيد التجهيز" حتى يُضاف المفتاح.
    if not os.environ.get("GROQ_API_KEY"):
        print(
            "تحذير: GROQ_API_KEY غير موجود — تخطّي الشرح. "
            "أضِف مفتاحاً مجانياً من console.groq.com كـ Secret باسم GROQ_API_KEY.",
            file=sys.stderr,
        )
        return

    from groq import Groq  # استيراد كسول: نحتاجه فقط عند وجود عمل فعلي

    client = Groq()
    print(f"مستودعات بحاجة لشرح: {len(pending)} (النموذج: {MODEL})")

    done = 0
    for repo in pending:
        print(f"  شرح: {repo['full_name']} ...")
        summary = summarize_one(client, repo)
        if summary:
            repo["summary_ar"] = summary
            done += 1
            save_repos(repos)  # حفظ تدريجي حتى لا نخسر التقدّم عند أي انقطاع
        else:
            print(f"    فشل شرح {repo['full_name']}، سيُعاد لاحقاً.", file=sys.stderr)

    print(f"تم شرح {done} مستودع.")


if __name__ == "__main__":
    main()
