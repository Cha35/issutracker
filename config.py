RSS_FEEDS = {
    "sports_soccer": [
        ("Google News 손흥민", "https://news.google.com/rss/search?q=손흥민&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News 이강인", "https://news.google.com/rss/search?q=이강인&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News EPL", "https://news.google.com/rss/search?q=EPL+프리미어리그&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News K리그", "https://news.google.com/rss/search?q=K리그&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News 월드컵", "https://news.google.com/rss/search?q=월드컵+축구대표팀&hl=ko&gl=KR&ceid=KR:ko"),
    ],
    "sports_baseball": [
        ("Google News KBO", "https://news.google.com/rss/search?q=KBO+야구&hl=ko&gl=KR&ceid=KR:ko"),
    ],
    "sports_basketball": [
        ("Google News NBA", "https://news.google.com/rss/search?q=NBA+농구&hl=ko&gl=KR&ceid=KR:ko"),
    ],
    "sports_golf": [
        ("Google News 골프", "https://news.google.com/rss/search?q=골프+PGA&hl=ko&gl=KR&ceid=KR:ko"),
    ],
    # 연예: 드라마 비중 줄이고 아이돌/예능 위주로 재편
    "entertainment_kpop": [
        ("Google News 아이돌컴백", "https://news.google.com/rss/search?q=아이돌+컴백+신보&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News 열애루머", "https://news.google.com/rss/search?q=연예인+열애+열애설&hl=ko&gl=KR&ceid=KR:ko"),
    ],
    "entertainment_show": [
        ("Google News 예능", "https://news.google.com/rss/search?q=예능+나는솔로+환승연애&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News 시상식", "https://news.google.com/rss/search?q=시상식+대상+후보&hl=ko&gl=KR&ceid=KR:ko"),
    ],
    "social": [
        ("Google News 사회이슈", "https://news.google.com/rss/search?q=사회이슈+커뮤니티+화제&hl=ko&gl=KR&ceid=KR:ko"),
        ("Google News 젠더직장", "https://news.google.com/rss/search?q=젠더+직장+취업&hl=ko&gl=KR&ceid=KR:ko"),
    ],
}

COMMUNITY_SOURCES = [
    {
        "name": "더쿠 인기글",
        "url": "https://theqoo.net/hot",
        "type": "theqoo",
    },
    {
        "name": "에펨코리아 인기글",
        "url": "https://www.fmkorea.com/index.php?mid=best",
        "type": "fmkorea",
    },
]

# 카테고리당 최대 수집 이슈 수 (균형 조정)
CATEGORY_MAX = {
    "sports_soccer": 20,
    "sports_baseball": 10,
    "sports_basketball": 8,
    "sports_golf": 6,
    "entertainment_kpop": 10,
    "entertainment_show": 8,
    "social": 10,
}

MARKET_TYPES = ["prediction", "vote", "ranking", "numeric", "timing"]

CATEGORY_LABELS = {
    "sports_soccer": "축구",
    "sports_baseball": "야구",
    "sports_basketball": "농구",
    "sports_golf": "골프",
    "entertainment_kpop": "K-pop/연예",
    "entertainment_show": "예능/시상식",
    "entertainment": "연예/엔터",  # 하위 호환
    "social": "사회/커뮤니티",
}
