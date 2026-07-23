"""يبني موقع site/index.html من data/repos.json.

موقع رسمي ثنائي اللغة (عربي/إنجليزي بزر تبديل)، بطاقات مختصرة مع تفاصيل قابلة للفتح،
عدّاد تنازلي للمسح القادم، ومحرّك SEO. الشرح نفسه يبقى بالعربي.
"""

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quality import is_junk_text

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "repos.json"
SITE_DIR = ROOT / "site"

CANONICAL = "https://hashemwebdesing-sudo.github.io/github-website-arabic/"
NEW_BADGE_HOURS = 36
TAGLINE_CAP = 150


def esc(text):
    return html.escape(text or "")


def format_date(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return ""


def is_new(fetched_at):
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() < NEW_BADGE_HOURS * 3600
    except Exception:
        return False


def first_sentence(text, cap=TAGLINE_CAP):
    """يستخرج جملة قصيرة تلخّص الهدف من نص الشرح."""
    if not text:
        return ""
    text = text.strip()
    parts = re.split(r"(?<=[.!؟\n])\s+", text)
    out = parts[0].strip() if parts else text
    if len(out) > cap:
        out = out[:cap].rsplit(" ", 1)[0].rstrip("،, ") + "…"
    return out


def tagline_of(repo, lang):
    s = repo.get("summary_ar" if lang == "ar" else "summary_en")
    if s and s.get("what"):
        return first_sentence(s["what"])
    if repo.get("description"):
        return repo["description"]
    return "الشرح قيد التجهيز…" if lang == "ar" else "Explanation coming soon…"


SECTIONS = {
    "ar": [
        ("ما هو المشروع", "what"),
        ("لماذا يتميّز", "why"),
        ("من يستفيد منه", "who"),
        ("كيف تجرّبه", "try"),
    ],
    "en": [
        ("What is it", "what"),
        ("Why it stands out", "why"),
        ("Who it's for", "who"),
        ("How to try it", "try"),
    ],
}
PENDING = {
    "ar": '<p class="pending">الشرح قيد التجهيز — سيظهر في المسح القادم.</p>',
    "en": '<p class="pending">Explanation is being generated — coming in the next scan.</p>',
}


def render_details(summary, lang):
    if not summary:
        return PENDING[lang]
    parts = []
    for label, key in SECTIONS[lang]:
        body = summary.get(key)
        if body:
            parts.append(
                f'<div class="sec"><h4>{esc(label)}</h4><p>{esc(body)}</p></div>'
            )
    return "\n".join(parts)


def is_visible(repo):
    """يُخفي المرفوضين من الحَكَم، والفئات المزعجة الواضحة (حتى قبل الحُكم)."""
    v = repo.get("verdict")
    if v is not None and not v.get("keep"):
        return False
    if is_junk_text(repo.get("name", ""), repo.get("description", ""), repo.get("topics")):
        return False
    return True


def category_chip(repo):
    v = repo.get("verdict") or {}
    cat = v.get("category") if v.get("keep") else None
    if not cat:
        return ""
    label = esc(cat.replace("-", " ").title())
    return f'<span class="cat">{label}</span>'


def render_card(repo):
    new_badge = (
        '<span class="badge-new" data-k="new_badge">New</span>'
        if is_new(repo.get("fetched_at", "")) else ""
    )
    lang = (
        f'<span class="lang"><i class="dot"></i>{esc(repo["language"])}</span>'
        if repo.get("language") else ""
    )
    url = esc(repo["html_url"])
    s_ar = repo.get("summary_ar")
    s_en = repo.get("summary_en")

    # الشرح الإنجليزي، ومع غيابه نرجع للعربي كي لا تظهر بطاقة فارغة
    details_ar = render_details(s_ar, "ar")
    details_en = render_details(s_en, "en") if s_en else details_ar

    return f"""
    <article class="card" data-repo="{esc(repo['full_name'])}">
      <div class="card-top">
        <h2 class="repo-name"><a href="{url}" target="_blank" rel="noopener">{esc(repo['full_name'])}</a> {new_badge}</h2>
        <button class="fav-btn" type="button" aria-label="Bookmark">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>
        </button>
      </div>
      <p class="tagline">
        <span class="lx lx-ar">{esc(tagline_of(repo, 'ar'))}</span>
        <span class="lx lx-en">{esc(tagline_of(repo, 'en'))}</span>
      </p>
      <div class="meta">
        {category_chip(repo)}
        <span class="stars">★ {repo['stars']:,}</span>
        {lang}
        <span class="date">{format_date(repo.get('created_at', ''))}</span>
      </div>
      <button class="details-toggle" type="button" aria-expanded="false">
        <span data-k="details_toggle">Details</span><i class="chev">⌄</i>
      </button>
      <div class="details">
        <div class="lx lx-ar">{details_ar}</div>
        <div class="lx lx-en">{details_en}</div>
      </div>
      <a class="btn-gh" href="{url}" target="_blank" rel="noopener"><span data-k="open_gh">Open on GitHub</span> ↗</a>
    </article>
    """


def build():
    if not DATA_FILE.exists():
        print("لا يوجد data/repos.json — شغّل fetch_repos.py أولاً.", file=sys.stderr)
        sys.exit(1)

    all_repos = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    repos = [r for r in all_repos if is_visible(r)]
    repos.sort(key=lambda r: r.get("fetched_at", ""), reverse=True)
    hidden = len(all_repos) - len(repos)

    cards = "\n".join(render_card(r) for r in repos)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = len(repos)

    page = (
        TEMPLATE
        .replace("%%CARDS%%", cards)
        .replace("%%UPDATED%%", updated)
        .replace("%%COUNT%%", str(count))
        .replace("%%CANONICAL%%", CANONICAL)
    )

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    (SITE_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {CANONICAL}sitemap.xml\n", encoding="utf-8"
    )
    (SITE_DIR / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{CANONICAL}</loc>"
        f"<lastmod>{datetime.now(timezone.utc).strftime('%Y-%m-%d')}</lastmod>"
        "<changefreq>hourly</changefreq></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    print(f"تم بناء الموقع: {count} مستودع ظاهر (أُخفي {hidden}) في site/index.html")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>GitHub Radar · رادار GitHub — أحدث المشاريع الصاعدة مشروحة بالعربي</title>
<meta name="description" content="اكتشف أحدث مستودعات GitHub التي تخطّت 200 نجمة، مشروحة بالعربي ببساطة: ما هو المشروع، لماذا يتميّز، ومن يستفيد منه. · Discover trending new GitHub repositories that crossed 200 stars, explained simply in Arabic.">
<meta name="keywords" content="GitHub, رادار, مشاريع مفتوحة المصدر, برمجة, شرح عربي, trending repositories, open source, Arabic">
<meta name="author" content="aijolabs.com">
<link rel="canonical" href="%%CANONICAL%%">

<meta property="og:type" content="website">
<meta property="og:title" content="GitHub Radar · رادار GitHub">
<meta property="og:description" content="أحدث مشاريع GitHub الصاعدة مشروحة بالعربي ببساطة. Trending GitHub projects, explained in Arabic.">
<meta property="og:url" content="%%CANONICAL%%">
<meta property="og:locale" content="ar_AR">
<meta property="og:locale:alternate" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="GitHub Radar · رادار GitHub">
<meta name="twitter:description" content="أحدث مشاريع GitHub الصاعدة مشروحة بالعربي ببساطة.">

<meta name="theme-color" content="#0d1117">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='14' fill='%230d1117' stroke='%232dd4bf' stroke-width='2'/%3E%3Cpath d='M16 16 L26 10' stroke='%232dd4bf' stroke-width='2' stroke-linecap='round'/%3E%3Ccircle cx='16' cy='16' r='2' fill='%232dd4bf'/%3E%3C/svg%3E">

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "GitHub Radar · رادار GitHub",
  "url": "%%CANONICAL%%",
  "description": "أحدث مستودعات GitHub الصاعدة مشروحة بالعربي ببساطة.",
  "inLanguage": ["ar", "en"],
  "author": { "@type": "Organization", "name": "aijolabs.com", "url": "https://aijolabs.com" }
}
</script>
</head>
<body>

<header class="topbar" id="top">
  <a class="brand" href="#top" aria-label="GitHub Radar">
    <span class="brand-mark" aria-hidden="true"></span>
    <span class="brand-name" data-k="brand">GitHub Radar</span>
  </a>
  <button class="lang-btn" id="lang-btn" type="button">EN</button>
</header>

<section class="hero">
  <h1 class="hero-title" data-k="hero_title">Discover GitHub's rising projects</h1>
  <p class="hero-sub" data-k="hero_sub">New repositories that crossed 200 stars, explained simply in Arabic.</p>

  <div class="hero-row">
    <div class="countdown" title="">
      <span class="cd-label" data-k="cd_label">Next scan in</span>
      <span class="cd-time" id="cd-time">--:--</span>
    </div>
    <div class="stats">
      <span><strong>%%COUNT%%</strong> <span data-k="stat_projects">projects tracked</span></span>
      <span class="sep">·</span>
      <span><span data-k="stat_updated">Updated</span> <time class="mono">%%UPDATED%%</time></span>
    </div>
  </div>
</section>

<nav class="controls">
  <div class="filters">
    <button class="filter-btn active" type="button" data-filter="all" data-k="filter_all">All</button>
    <button class="filter-btn" type="button" data-filter="fav">
      <span data-k="filter_fav">Favorites</span> <span class="fav-count" id="fav-count">0</span>
    </button>
  </div>
  <input id="search" class="search-box" type="search" autocomplete="off"
         data-k-ph="search_ph" aria-label="Search">
</nav>

<p id="empty-favs" class="notice" data-k="empty_favs" hidden>No bookmarks yet.</p>
<p id="no-results" class="notice" data-k="no_results" hidden>No results.</p>

<main class="grid">
%%CARDS%%
</main>

<footer class="site-foot">
  <p class="foot-auto" data-k="foot_auto">Auto-updates every 10 minutes via GitHub Actions.</p>
  <p class="foot-by">
    <span data-k="foot_by">Designed &amp; developed by</span>
    <a href="https://aijolabs.com" target="_blank" rel="noopener">aijolabs.com</a>
  </p>
</footer>

<script>
(function () {
  /* ---------- i18n ---------- */
  var I18N = {
    ar: {
      brand: "رادار GitHub",
      hero_title: "اكتشف أقوى مشاريع GitHub الجديدة",
      hero_sub: "المستودعات الجديدة التي تخطّت ٢٠٠ نجمة — مشروحة لك بالعربي ببساطة.",
      cd_label: "المسح القادم بعد",
      stat_projects: "مشروع مُتابَع",
      stat_updated: "آخر تحديث",
      filter_all: "الكل",
      filter_fav: "المفضلة",
      search_ph: "ابحث… (python، بيانات، مواقع)",
      details_toggle: "التفاصيل",
      open_gh: "افتح على GitHub",
      new_badge: "جديد",
      empty_favs: "لا يوجد مفضلة بعد. اضغط أيقونة الإشارة المرجعية على أي بطاقة لحفظها والرجوع إليها لاحقاً.",
      no_results: "لا توجد نتائج تطابق بحثك. جرّب كلمة أخرى.",
      foot_auto: "يُحدَّث تلقائياً كل ١٠ دقائق عبر GitHub Actions.",
      foot_by: "صُمّم وطُوِّر بواسطة",
      lang_switch: "EN"
    },
    en: {
      brand: "GitHub Radar",
      hero_title: "Discover GitHub's rising projects",
      hero_sub: "New repositories that crossed 200 stars — explained simply, in Arabic.",
      cd_label: "Next scan in",
      stat_projects: "projects tracked",
      stat_updated: "Updated",
      filter_all: "All",
      filter_fav: "Favorites",
      search_ph: "Search… (python, data, tools)",
      details_toggle: "Details",
      open_gh: "Open on GitHub",
      new_badge: "New",
      empty_favs: "No bookmarks yet. Tap the bookmark icon on any card to save it for later.",
      no_results: "No results match your search. Try another keyword.",
      foot_auto: "Auto-updates every 10 minutes via GitHub Actions.",
      foot_by: "Designed & developed by",
      lang_switch: "عربي"
    }
  };
  var LKEY = "radar_lang";
  var lang = localStorage.getItem(LKEY) || "ar";

  function applyLang() {
    var dict = I18N[lang];
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-k]").forEach(function (el) {
      var v = dict[el.dataset.k];
      if (v != null) el.textContent = v;
    });
    document.querySelectorAll("[data-k-ph]").forEach(function (el) {
      var v = dict[el.dataset.kPh];
      if (v != null) el.placeholder = v;
    });
    document.getElementById("lang-btn").textContent = dict.lang_switch;
  }
  document.getElementById("lang-btn").addEventListener("click", function () {
    lang = lang === "ar" ? "en" : "ar";
    localStorage.setItem(LKEY, lang);
    applyLang();
  });

  /* ---------- countdown to next 10-minute mark ---------- */
  var cdEl = document.getElementById("cd-time");
  function tickCountdown() {
    var now = new Date();
    var secsIntoBlock = (now.getMinutes() % 10) * 60 + now.getSeconds();
    var left = 600 - secsIntoBlock;
    var m = Math.floor(left / 60);
    var s = left % 60;
    cdEl.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
  }
  tickCountdown();
  setInterval(tickCountdown, 1000);

  /* ---------- favorites + search + filter ---------- */
  var FKEY = "radar_favs";
  var currentFilter = "all";
  var query = "";

  function getFavs() {
    try { return JSON.parse(localStorage.getItem(FKEY)) || []; }
    catch (e) { return []; }
  }
  function setFavs(list) { localStorage.setItem(FKEY, JSON.stringify(list)); }
  function updateCount() {
    document.getElementById("fav-count").textContent = getFavs().length;
  }

  var cards = [].slice.call(document.querySelectorAll(".card"));
  cards.forEach(function (card) { card._text = (card.textContent || "").toLowerCase(); });

  function applyView() {
    var favs = getFavs();
    var q = query.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (card) {
      var passFilter = currentFilter === "all" || favs.indexOf(card.dataset.repo) !== -1;
      var passSearch = q === "" || card._text.indexOf(q) !== -1;
      var show = passFilter && passSearch;
      card.style.display = show ? "" : "none";
      if (show) shown++;
    });
    document.getElementById("empty-favs").hidden =
      !(currentFilter === "fav" && q === "" && shown === 0);
    document.getElementById("no-results").hidden = !(q !== "" && shown === 0);
  }

  cards.forEach(function (card) {
    var repo = card.dataset.repo;
    var fav = card.querySelector(".fav-btn");
    if (getFavs().indexOf(repo) !== -1) fav.classList.add("saved");
    fav.addEventListener("click", function () {
      var favs = getFavs();
      var i = favs.indexOf(repo);
      if (i !== -1) { favs.splice(i, 1); fav.classList.remove("saved"); }
      else { favs.push(repo); fav.classList.add("saved"); }
      setFavs(favs); updateCount(); applyView();
    });

    var toggle = card.querySelector(".details-toggle");
    toggle.addEventListener("click", function () {
      var open = card.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  document.querySelectorAll(".filter-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".filter-btn").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      currentFilter = btn.dataset.filter;
      applyView();
    });
  });

  document.getElementById("search").addEventListener("input", function (e) {
    query = e.target.value;
    applyView();
  });

  applyLang();
  updateCount();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
