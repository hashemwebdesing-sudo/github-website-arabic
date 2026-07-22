# 📡 رادار GitHub بالعربي

موقع يرصد **أحدث المشاريع المميزة** على GitHub — اللي وصلت **٢٠٠ نجمة فأكثر** خلال أيام من إنشائها — ويشرح كل مشروع **بالعربي**: شو هو، ليش مميز، مين يستفيد منه، وكيف تجرّبه.

الفكرة بسيطة: بدل ما تسمع عن المشاريع المميزة متأخر ومن غيرك، الموقع بيجيبها لك أول بأول ويشرحها لك بلغتك.

## كيف يشتغل؟

الموقع يتحدّث **تلقائياً كل يوم** بدون أي تدخل، عبر ثلاث خطوات:

1. **`fetch_repos.py`** — يبحث في GitHub عن المستودعات المنشأة حديثاً اللي وصلت ٢٠٠ نجمة فأكثر، ويجيب ملف الـ README لكل واحد جديد.
2. **`summarize.py`** — يقرأ كل مستودع جديد ويولّد له شرحاً عربياً واضحاً عبر الذكاء الاصطناعي (Claude).
3. **`build_site.py`** — يبني صفحة الموقع من البيانات، ويُنشر على GitHub Pages.

كل هذا يشتغل مجاناً عبر **GitHub Actions** — بدون سيرفر وبدون تكلفة استضافة.

## التقنيات

- **Python** — السكربتات الثلاثة
- **GitHub Search API** — لجلب المستودعات (مجاني)
- **Claude API (Haiku)** — لتوليد الشرح العربي (تكلفة رمزية، أقل من دولار شهرياً)
- **GitHub Actions + Pages** — للأتمتة والنشر المجاني

## التشغيل محلياً

```bash
pip install -r requirements.txt

# مفتاح Claude من https://console.anthropic.com
export ANTHROPIC_API_KEY="your-key-here"

python scripts/fetch_repos.py     # يجلب المستودعات الجديدة
python scripts/summarize.py       # يولّد الشرح العربي
python scripts/build_site.py      # يبني الموقع في مجلد site/
```

> على ويندوز (PowerShell) استبدل `export` بـ `$env:ANTHROPIC_API_KEY="your-key-here"`

لتجربة عدد محدود من المستودعات (توفيراً للتكلفة): `SUMMARIZE_LIMIT=3`

## الإعداد على GitHub

1. ارفع المشروع إلى مستودع عام على GitHub.
2. من **Settings → Secrets and variables → Actions** أضِف سراً باسم `ANTHROPIC_API_KEY`.
3. من **Settings → Pages** اختر المصدر **GitHub Actions**.
4. شغّل الـ workflow يدوياً من تبويب **Actions** (زر *Run workflow*) أو انتظر التشغيل اليومي.

---

الشرح مولّد بالذكاء الاصطناعي، وقد يحتوي على أخطاء بسيطة — تحقّق دائماً من المصدر الأصلي.
