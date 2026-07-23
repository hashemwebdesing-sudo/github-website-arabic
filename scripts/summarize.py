"""يولّد شرحاً عربياً وإنجليزياً لكل مستودع، عبر Groq (نماذج Llama — سريعة ومجانية).

يملأ الحقلين summary_ar و summary_en للمستودعات الناقصة، ثم يحفظ.
فشل مستودع واحد لا يوقف الباقي، ولا يُعاد توليد ما تم توليده.

يحتاج GROQ_API_KEY (مفتاح مجاني من https://console.groq.com). النموذج عبر GROQ_MODEL.
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
LIMIT = int(os.environ.get("SUMMARIZE_LIMIT", "0"))  # 0 = بلا حد

REQUIRED_KEYS = ("what", "why", "who", "try")

PROMPT_AR = """أنت خبير تقني تشرح مشاريع GitHub لشخص عربي يحب التقنية لكنه ضعيف بالإنجليزي.
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

PROMPT_EN = """You are a technical expert explaining a GitHub project to a curious developer in simple, clear English.

Repository: {full_name}
Language: {language}
Official description: {description}
Stars: {stars}

README excerpt:
---
{readme}
---

Return your answer as **JSON only** (no text outside the JSON), exactly like this:
{{
  "what": "What is this project? Two simple sentences.",
  "why": "Why it stands out and why people are excited / it gained stars so fast.",
  "who": "Who benefits from it.",
  "try": "How to try it — brief steps or install commands."
}}
All values in English. Do not add any text or comments outside the JSON."""

PROMPTS = {"ar": PROMPT_AR, "en": PROMPT_EN}


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


def summarize_one(client, repo, lang):
    prompt = PROMPTS[lang].format(
        full_name=repo["full_name"],
        language=repo["language"] or "unspecified",
        description=repo["description"] or "no description",
        stars=repo["stars"],
        readme=repo["readme"] or "no README",
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
            data = json.loads(response.choices[0].message.content)
            if not valid_summary(data) and len(data) == 1:
                inner = next(iter(data.values()))
                if valid_summary(inner):
                    data = inner
            if valid_summary(data):
                return {k: data[k].strip() for k in REQUIRED_KEYS}
            print("    ناتج غير مكتمل، إعادة المحاولة...", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            wait = min(2 ** attempt, 30)
            print(f"    خطأ ({type(e).__name__}): {e} — انتظار {wait}ث", file=sys.stderr)
            time.sleep(wait)
    return None


def needs_work(repo):
    return repo.get("summary_ar") is None or repo.get("summary_en") is None


def main():
    repos = load_repos()
    pending = [r for r in repos if needs_work(r)]
    if LIMIT > 0:
        pending = pending[:LIMIT]

    if not pending:
        print("لا يوجد مستودعات بحاجة لشرح.")
        return

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
        for lang, field in (("ar", "summary_ar"), ("en", "summary_en")):
            if repo.get(field) is not None:
                continue
            print(f"  [{lang}] {repo['full_name']} ...")
            summary = summarize_one(client, repo, lang)
            if summary:
                repo[field] = summary
                done += 1
                save_repos(repos)  # حفظ تدريجي
            else:
                print(f"    فشل [{lang}] {repo['full_name']}، سيُعاد لاحقاً.", file=sys.stderr)

    print(f"تم توليد {done} شرح.")


if __name__ == "__main__":
    main()
