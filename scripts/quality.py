"""قواعد جودة مشتركة بين جلب المستودعات، الحَكَم، وبناء الموقع.

الطبقة الأولى (قواعد سريعة): كلمات مفتاحية تستبعد الفئات المزعجة الواضحة.
الطبقة الثانية (الحَكَم الذكي في summarize.py) تعتمد على JUNK_CATEGORIES و QUALITY_MIN.
"""

# كلمات تدلّ على فئات نستبعدها فوراً (كريبتو/تحايل شبكات/قمار/إباحي/غش).
# محافِظة عمداً لتقليل الاستبعاد الخاطئ — الحَكَم الذكي يمسك الباقي.
BLOCKLIST = [
    # كريبتو / تداول
    "mev", "arbitrage", "airdrop", "memecoin", "meme coin", "pump.fun",
    "wallet drainer", "sniper bot", "trading bot", "web3 casino",
    # لوحات تحايل / VPN
    "v2ray", "xray-core", "marzban", "shadowsocks", "sing-box",
    "hysteria2", "trojan-go", "clash-verge", "vpn panel", "free vpn",
    # قمار / محتوى للبالغين / إساءة
    "casino", "gambling", "betting", "nsfw", "onlyfans", "porn",
    "aimbot", "game cheat", "auto liker", "free followers",
]

# فئات يعيدها الحَكَم الذكي وتعني الرفض التلقائي مهما كانت الدرجة.
JUNK_CATEGORIES = {
    "crypto", "vpn-proxy", "gambling", "nsfw",
    "game-cheat", "reskin", "fake-or-joke", "spam",
}

# فئات مقبولة (لتوجيه الحَكَم وعرضها كوسم على البطاقة).
GOOD_CATEGORIES = [
    "developer-tool", "library", "framework", "application",
    "ai-ml", "data", "security", "learning", "design",
    "infrastructure", "other",
]

QUALITY_MIN = 5  # أقل درجة جودة مقبولة (1-10)


def is_junk_text(name, description, topics=None):
    """True إذا طابق الاسم/الوصف/الوسوم أي كلمة في قائمة الاستبعاد."""
    hay = " ".join([
        name or "",
        description or "",
        " ".join(topics or []),
    ]).lower()
    return any(kw in hay for kw in BLOCKLIST)
