"""يولّد شرحاً عربياً وإنجليزياً لكل مستودع، عبر Groq (نماذج Llama — سريعة ومجانية).

يملأ الحقلين summary_ar و summary_en للمستودعات الناقصة، ثم يحفظ.
فشل مستودع واحد لا يوقف الباقي، ولا يُعاد توليد ما تم توليده.

يحتاج GROQ_API_KEY (مفتاح مجاني من https://console.groq.com). النموذج عبر GROQ_MODEL.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality import JUNK_CATEGORIES, QUALITY_MIN, GOOD_CATEGORIES
from httputil import post_json

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"

MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = 1200
MAX_RETRIES = 4
RATE_RETRIES = 8  # محاولات إضافية عند تجاوز حد الطلبات (429)
LIMIT = int(os.environ.get("SUMMARIZE_LIMIT", "0"))  # 0 = بلا حد
# نقتطع README لتقليل التوكن المُرسَل (أهم عامل لتفادي حد Groq المجاني)
README_LIMIT = int(os.environ.get("README_CHARS", "1500"))

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

اعتمد **فقط** على المعلومات الموجودة في الوصف والـ README. لا تخترع أسماء شركات أو مطوّرين أو ميزات غير مذكورة.

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

Base your answer **only** on the description and README. Do not invent company names, authors, or features that are not stated.

Return your answer as **JSON only** (no text outside the JSON), exactly like this:
{{
  "what": "What is this project? Two simple sentences.",
  "why": "Why it stands out and why people are excited / it gained stars so fast.",
  "who": "Who benefits from it.",
  "try": "How to try it — brief steps or install commands."
}}
All values in English. Do not add any text or comments outside the JSON."""

PROMPTS = {"ar": PROMPT_AR, "en": PROMPT_EN}

JUDGE_PROMPT = """You are a strict curator for a site that features genuinely useful, substantial open-source GitHub projects for developers. Decide if this repository deserves to be featured.

Repository: {full_name}
Description: {description}
Language: {language}
Stars: {stars}
Topics: {topics}

README excerpt:
---
{readme}
---

REJECT (keep=false) if it is any of: cryptocurrency / trading / MEV / airdrop; VPN / proxy / censorship-circumvention panel; gambling or betting; NSFW; a cheat or exploit for games; a low-effort reskin or theme wrapper around another product; a joke / fake / troll repo; spam; or anything with no real engineering substance.
KEEP (keep=true) only if it is a real, substantial, useful project (developer tool, library, framework, application, AI/ML, data, security, learning resource, design or infrastructure tool).

Return JSON ONLY, exactly:
{{
  "keep": true,
  "category": "one of: {categories}",
  "quality": 7,
  "reason": "one short sentence"
}}
No text outside the JSON."""


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


def call_groq(prompt, max_tokens, temperature):
    """يرسل طلباً لـ Groq ويُعيد نص المحتوى، مع انتظار ذكي عند حد الطلبات (429)."""
    payload = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
    for _ in range(RATE_RETRIES):
        status, data = post_json(GROQ_URL, payload, headers)
        if status == 200:
            time.sleep(0.4)  # تهدئة بسيطة بين الطلبات
            return data["choices"][0]["message"]["content"]
        if status == 429:
            # نستخرج مدة الانتظار المقترحة من رسالة Groq (وإلا 20ث)
            msg = json.dumps(data, ensure_ascii=False)
            m = re.search(r"try again in ([\d.]+)s", msg)
            wait = (float(m.group(1)) + 1.5) if m else 20
            print(f"    حد Groq — انتظار {wait:.0f}ث", file=sys.stderr)
            time.sleep(wait)
            continue
        raise RuntimeError(f"Groq رجّع {status}: {str(data)[:200]}")
    raise RuntimeError("Groq: تجاوز الحد بشكل متكرر (429)")


def summarize_one(repo, lang):
    prompt = PROMPTS[lang].format(
        full_name=repo["full_name"],
        language=repo["language"] or "unspecified",
        description=repo["description"] or "no description",
        stars=repo["stars"],
        readme=(repo["readme"] or "no README")[:README_LIMIT],
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = json.loads(call_groq(prompt, MAX_TOKENS, 0.4))
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


def judge_one(repo):
    prompt = JUDGE_PROMPT.format(
        full_name=repo["full_name"],
        description=repo["description"] or "no description",
        language=repo["language"] or "unspecified",
        stars=repo["stars"],
        topics=", ".join(repo.get("topics") or []) or "none",
        readme=(repo["readme"] or "no README")[:README_LIMIT],
        categories=", ".join(GOOD_CATEGORIES + sorted(JUNK_CATEGORIES)),
    )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            v = json.loads(call_groq(prompt, 300, 0.2))
            keep = bool(v.get("keep"))
            category = str(v.get("category", "other")).strip().lower()
            try:
                quality = int(v.get("quality", 0))
            except (TypeError, ValueError):
                quality = 0
            # فرض القواعد: فئة مرفوضة أو جودة منخفضة = رفض مهما قال الحَكَم
            if category in JUNK_CATEGORIES or quality < QUALITY_MIN:
                keep = False
            return {
                "keep": keep,
                "category": category,
                "quality": quality,
                "reason": str(v.get("reason", ""))[:200],
            }
        except Exception as e:  # noqa: BLE001
            wait = min(2 ** attempt, 30)
            print(f"    خطأ حَكَم ({type(e).__name__}): {e} — انتظار {wait}ث", file=sys.stderr)
            time.sleep(wait)
    return None


def needs_work(repo):
    v = repo.get("verdict")
    if v is None:
        return True                       # بحاجة لحُكم
    if not v.get("keep"):
        return False                      # مرفوض — لا عمل إضافي
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

    print(f"مستودعات بحاجة لمعالجة: {len(pending)} (النموذج: {MODEL})")

    judged = summarized = rejected = 0
    for repo in pending:
        # ١) الحَكَم أولاً — لتوفير مكالمات الشرح على المرفوضين
        if repo.get("verdict") is None:
            verdict = judge_one(repo)
            if not verdict:
                print(f"    فشل حُكم {repo['full_name']}، سيُعاد لاحقاً.", file=sys.stderr)
                continue
            repo["verdict"] = verdict
            judged += 1
            save_repos(repos)
            mark = "✓" if verdict["keep"] else f"✗ ({verdict['category']})"
            print(f"  حُكم: {repo['full_name']} → {mark} جودة {verdict['quality']}")

        if not repo["verdict"].get("keep"):
            rejected += 1
            continue

        # ٢) الشرح ثنائي اللغة للمقبولين فقط
        for lang, field in (("ar", "summary_ar"), ("en", "summary_en")):
            if repo.get(field) is not None:
                continue
            print(f"  [{lang}] {repo['full_name']} ...")
            summary = summarize_one(repo, lang)
            if summary:
                repo[field] = summary
                summarized += 1
                save_repos(repos)
            else:
                print(f"    فشل [{lang}] {repo['full_name']}، سيُعاد لاحقاً.", file=sys.stderr)

    print(f"حُكم على {judged} · رُفض {rejected} · وُلّد {summarized} شرح.")


if __name__ == "__main__":
    main()
