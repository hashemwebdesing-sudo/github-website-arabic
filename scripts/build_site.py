"""يبني موقع site/index.html من data/repos.json — عربي RTL، بطاقات لكل مستودع."""

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"
SITE_DIR = ROOT / "site"

NEW_BADGE_HOURS = 36  # يظهر شارة "جديد" لما أُضيف خلال هذه المدة


def esc(text):
    return html.escape(text or "")


def format_date(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def is_new(fetched_at):
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - dt
        return age.total_seconds() < NEW_BADGE_HOURS * 3600
    except Exception:
        return False


def render_summary(summary):
    if not summary:
        return '<p class="pending">⏳ الشرح قيد التجهيز...</p>'
    sections = [
        ("💡 شو هو المشروع؟", summary.get("what")),
        ("⭐ ليش مميز؟", summary.get("why")),
        ("👥 مين يستفيد منه؟", summary.get("who")),
        ("🚀 كيف تجرّبه؟", summary.get("try")),
    ]
    parts = []
    for title, body in sections:
        if body:
            parts.append(
                f'<div class="sec"><h4>{esc(title)}</h4><p>{esc(body)}</p></div>'
            )
    return "\n".join(parts)


def render_card(repo):
    badge = '<span class="badge-new">جديد</span>' if is_new(repo.get("fetched_at", "")) else ""
    lang = f'<span class="lang">{esc(repo["language"])}</span>' if repo.get("language") else ""
    return f"""
    <article class="card" data-repo="{esc(repo['full_name'])}">
      <header class="card-head">
        <div class="title-row">
          <h2><a href="{esc(repo['html_url'])}" target="_blank" rel="noopener">{esc(repo['full_name'])}</a> {badge}</h2>
          <button class="fav-btn" type="button" aria-label="احفظ في المفضلة" title="احفظ في المفضلة">🔖</button>
        </div>
        <div class="meta">
          <span class="stars">⭐ {repo['stars']:,}</span>
          {lang}
          <span class="date">أُنشئ: {format_date(repo.get('created_at', ''))}</span>
        </div>
      </header>
      {f'<p class="desc-en">{esc(repo["description"])}</p>' if repo.get('description') else ''}
      <div class="summary">{render_summary(repo.get('summary_ar'))}</div>
      <a class="btn" href="{esc(repo['html_url'])}" target="_blank" rel="noopener">افتح على GitHub ↗</a>
    </article>
    """


def build():
    if not DATA_FILE.exists():
        print("لا يوجد data/repos.json — شغّل fetch_repos.py أولاً.", file=sys.stderr)
        sys.exit(1)

    repos = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    # الأحدث إضافةً أولاً
    repos.sort(key=lambda r: r.get("fetched_at", ""), reverse=True)

    cards = "\n".join(render_card(r) for r in repos)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = len(repos)

    page = TEMPLATE.format(cards=cards, updated=updated, count=count)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"تم بناء الموقع: {count} مستودع في site/index.html")


TEMPLATE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>رادار GitHub بالعربي — أحدث المشاريع المميزة مشروحة</title>
<meta name="description" content="أحدث مستودعات GitHub المميزة التي وصلت 200 نجمة فأكثر، مشروحة بالعربي: شو المشروع، ليش مميز، ومين يستفيد منه.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="site-head">
  <h1>📡 رادار GitHub بالعربي</h1>
  <p class="tagline">أحدث المشاريع المميزة على GitHub — اللي وصلت ٢٠٠ نجمة فأكثر — مشروحة لك بالعربي.</p>
  <p class="stats">🗂️ {count} مشروع · آخر تحديث: {updated}</p>
</header>

<nav class="toolbar">
  <button class="filter-btn active" type="button" data-filter="all">الكل</button>
  <button class="filter-btn" type="button" data-filter="fav">🔖 مفضلتي (<span id="fav-count">0</span>)</button>
</nav>

<p id="empty-favs" class="empty-favs" hidden>
  ما عندك أي مستودع بالمفضلة بعد. اضغط على أيقونة 🔖 فوق أي بطاقة لتحفظها وترجعلها لاحقاً.
</p>

<main class="grid">
{cards}
</main>

<footer class="site-foot">
  <p>يتحدّث تلقائياً كل يوم عبر GitHub Actions · الشرح مولّد بالذكاء الاصطناعي (Claude)</p>
  <p class="foot-note">مفضلتك محفوظة داخل متصفحك على هذا الجهاز فقط.</p>
</footer>

<script>
(function () {{
  var KEY = "radar_favs";
  var currentFilter = "all";

  function getFavs() {{
    try {{ return JSON.parse(localStorage.getItem(KEY)) || []; }}
    catch (e) {{ return []; }}
  }}
  function setFavs(list) {{ localStorage.setItem(KEY, JSON.stringify(list)); }}
  function updateCount() {{
    document.getElementById("fav-count").textContent = getFavs().length;
  }}

  function applyFilter(mode) {{
    var favs = getFavs();
    var shown = 0;
    document.querySelectorAll(".card").forEach(function (card) {{
      var isFav = favs.indexOf(card.dataset.repo) !== -1;
      var show = mode === "all" || isFav;
      card.style.display = show ? "" : "none";
      if (show) shown++;
    }});
    var empty = document.getElementById("empty-favs");
    empty.hidden = !(mode === "fav" && shown === 0);
  }}

  // تجهيز أزرار الحفظ على كل بطاقة
  document.querySelectorAll(".card").forEach(function (card) {{
    var repo = card.dataset.repo;
    var btn = card.querySelector(".fav-btn");
    if (getFavs().indexOf(repo) !== -1) btn.classList.add("saved");
    btn.addEventListener("click", function () {{
      var favs = getFavs();
      var idx = favs.indexOf(repo);
      if (idx !== -1) {{ favs.splice(idx, 1); btn.classList.remove("saved"); }}
      else {{ favs.push(repo); btn.classList.add("saved"); }}
      setFavs(favs);
      updateCount();
      if (currentFilter === "fav") applyFilter("fav");
    }});
  }});

  // أزرار الفلترة
  document.querySelectorAll(".filter-btn").forEach(function (btn) {{
    btn.addEventListener("click", function () {{
      document.querySelectorAll(".filter-btn").forEach(function (b) {{
        b.classList.remove("active");
      }});
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      applyFilter(currentFilter);
    }});
  }});

  updateCount();
}})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
