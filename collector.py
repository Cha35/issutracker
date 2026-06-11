import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import time
from config import RSS_FEEDS, COMMUNITY_SOURCES, CATEGORY_MAX

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}


def fetch_rss(category, sources, since_hours=24):
    items = []
    cutoff = datetime.now() - timedelta(hours=since_hours)

    for source_name, url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])

                if published and published < cutoff:
                    continue

                items.append({
                    "title": entry.get("title", "").strip(),
                    "summary": BeautifulSoup(entry.get("summary", ""), "html.parser").get_text()[:300].strip(),
                    "link": entry.get("link", ""),
                    "published": published.isoformat() if published else datetime.now().isoformat(),
                    "source": source_name,
                    "category": category,
                })
            time.sleep(0.5)
        except Exception as e:
            print(f"  [오류] {source_name}: {e}")

    return items


def fetch_theqoo(url):
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.select("table.bd_lst tr td.title a")[:20]
        for post in posts:
            title = post.get_text(strip=True)
            link = "https://theqoo.net" + post.get("href", "")
            if title:
                items.append({
                    "title": title,
                    "summary": "",
                    "link": link,
                    "published": datetime.now().isoformat(),
                    "source": "더쿠 인기글",
                    "category": "social",
                })
    except Exception as e:
        print(f"  [오류] 더쿠: {e}")
    return items


def fetch_fmkorea(url):
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.select("li.li_best2_items0 a.title, li.li_best2_items1 a.title")[:20]
        for post in posts:
            title = post.get_text(strip=True)
            href = post.get("href", "")
            link = "https://www.fmkorea.com" + href if href.startswith("/") else href
            if title:
                items.append({
                    "title": title,
                    "summary": "",
                    "link": link,
                    "published": datetime.now().isoformat(),
                    "source": "에펨코리아 인기글",
                    "category": "social",
                })
    except Exception as e:
        print(f"  [오류] 에펨코리아: {e}")
    return items


def collect_all(since_hours=24):
    all_items = []

    print("=== RSS 피드 수집 중 ===")
    for category, sources in RSS_FEEDS.items():
        print(f"[{category}] 수집 중...")
        items = fetch_rss(category, sources, since_hours)
        # 카테고리별 최대 수 제한
        max_count = CATEGORY_MAX.get(category, 20)
        if len(items) > max_count:
            items = items[:max_count]
        print(f"  → {len(items)}개 수집")
        all_items.extend(items)

    print("\n=== 커뮤니티 수집 중 ===")
    for source in COMMUNITY_SOURCES:
        print(f"[{source['name']}] 수집 중...")
        if source["type"] == "theqoo":
            items = fetch_theqoo(source["url"])
        elif source["type"] == "fmkorea":
            items = fetch_fmkorea(source["url"])
        else:
            items = []
        print(f"  → {len(items)}개 수집")
        all_items.extend(items)

    seen = set()
    unique_items = []
    for item in all_items:
        if item["title"] not in seen and len(item["title"]) > 5:
            seen.add(item["title"])
            unique_items.append(item)

    print(f"\n총 {len(unique_items)}개 이슈 수집 완료 (중복 제거 후)")
    return unique_items


if __name__ == "__main__":
    items = collect_all()
    with open("collected_issues.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print("collected_issues.json 저장 완료")
