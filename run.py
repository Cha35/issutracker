"""
폴리볼 이슈 수집 자동화 메인 실행 파일
사용법: python run.py [--hours 24] [--no-collect] [--no-process]
"""
import argparse
import json
import os
import webbrowser
from datetime import datetime

from collector import collect_all
from processor import process_batch, filter_and_sort, enrich_with_links, deduplicate_markets, generate_creative_markets
from dashboard import build_dashboard


def load_locked_markets():
    path = "locked_markets.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            locked = json.load(f)
            print(f"  🔒 잠금 마켓 {len(locked)}개 보존")
            return locked
    return []


def save_history(date_str, issues, markets):
    os.makedirs("history", exist_ok=True)
    issues_path = f"history/{date_str}_issues.json"
    markets_path = f"history/{date_str}_markets.json"

    # 이슈: 기존 파일 있으면 병합 (중복 제거)
    existing_issues = []
    if os.path.exists(issues_path):
        with open(issues_path, encoding="utf-8") as f:
            existing_issues = json.load(f)
    seen_titles = {i["title"] for i in existing_issues}
    merged_issues = existing_issues + [i for i in issues if i["title"] not in seen_titles]
    with open(issues_path, "w", encoding="utf-8") as f:
        json.dump(merged_issues, f, ensure_ascii=False, indent=2)

    # 마켓: 덮어쓰기
    with open(markets_path, "w", encoding="utf-8") as f:
        json.dump(markets, f, ensure_ascii=False, indent=2)

    print(f"→ history/{date_str} 저장 완료")


def main():
    parser = argparse.ArgumentParser(description="폴리볼 이슈 수집 & 마켓 초안 생성")
    parser.add_argument("--hours", type=int, default=24, help="몇 시간 이내 이슈 수집 (기본: 24)")
    parser.add_argument("--no-collect", action="store_true", help="수집 단계 건너뛰기 (기존 JSON 사용)")
    parser.add_argument("--no-process", action="store_true", help="AI 처리 단계 건너뛰기")
    parser.add_argument("--open", action="store_true", help="완료 후 대시보드 자동 열기")
    args = parser.parse_args()

    start = datetime.now()
    date_str = start.strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"폴리볼 이슈 수집기 시작: {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    if not args.no_collect:
        print("[ 1단계 ] 뉴스 & 커뮤니티 이슈 수집")
        issues = collect_all(since_hours=args.hours)
        with open("collected_issues.json", "w", encoding="utf-8") as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)
        print(f"→ collected_issues.json 저장 ({len(issues)}개)\n")
    else:
        print("[ 1단계 ] 수집 건너뜀 (기존 데이터 사용)\n")
        with open("collected_issues.json", encoding="utf-8") as f:
            issues = json.load(f)

    markets = []
    if not args.no_process:
        if not os.environ.get("GEMINI_API_KEY"):
            print("[경고] GEMINI_API_KEY가 없습니다. .env 파일을 확인하세요.")
            print("  → AI 처리 단계를 건너뜁니다.\n")
        else:
            print("[ 2단계 ] AI 마켓 초안 생성")
            # 잠금 마켓 로드
            locked = load_locked_markets()
            locked_questions = {m.get("question", "") for m in locked}

            markets = process_batch(issues)
            markets = enrich_with_links(markets, issues)

            # 자유 마켓 생성
            creative = generate_creative_markets(issues, count=15)
            markets = markets + creative

            # 잠금 마켓 제외 후 중복 제거 + 필터
            markets = [m for m in markets if m.get("question", "") not in locked_questions]
            markets = deduplicate_markets(markets)
            markets = filter_and_sort(markets)

            # 잠금 마켓을 맨 앞에 붙여서 보존
            markets = locked + markets
            with open("market_drafts.json", "w", encoding="utf-8") as f:
                json.dump(markets, f, ensure_ascii=False, indent=2)
            print(f"→ market_drafts.json 저장 ({len(markets)}개)\n")
    else:
        print("[ 2단계 ] AI 처리 건너뜀\n")
        if os.path.exists("market_drafts.json"):
            with open("market_drafts.json", encoding="utf-8") as f:
                markets = json.load(f)

    # 히스토리 저장
    save_history(date_str, issues, markets)

    print("[ 3단계 ] 대시보드 생성")
    path = build_dashboard()

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"완료! 소요시간: {elapsed}초")
    print(f"{'='*50}")

    if args.open and path:
        webbrowser.open(f"file:///{os.path.abspath(path)}")


if __name__ == "__main__":
    main()
