"""
폴리볼 이슈 수집 자동화 메인 실행 파일
사용법: python run.py [--hours 24] [--no-collect] [--no-process]
"""
import sys
import io
# Windows cp949 콘솔에서 UTF-8 출력 강제 (이모지/화살표 깨짐 방지)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import os
import subprocess
import webbrowser
from datetime import datetime

import engine
from processor import filter_and_sort, deduplicate_markets
from dashboard import build_dashboard

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def deploy_to_git():
    """동기화 결과(index.html)를 git push → Vercel 자동 배포.
    변경 없으면 스킵, 실패해도 동기화 자체는 깨지지 않음."""
    print("[ 4단계 ] 배포 (git push → Vercel)")
    files = ["index.html", "dashboard.html"]
    # Windows cp949 콘솔에서 git의 UTF-8(한글) 출력 디코딩 깨짐 방지
    gk = {"cwd": BASE_DIR, "capture_output": True, "text": True,
          "encoding": "utf-8", "errors": "replace"}
    try:
        subprocess.run(["git", "add"] + files, check=True, **gk)
        # 스테이징된 변경이 없으면 returncode 0 → 스킵
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR)
        if diff.returncode == 0:
            print("  → 변경사항 없음, 배포 스킵")
            return
        msg = f"sync: {datetime.now().strftime('%Y-%m-%d %H:%M')} 마켓 갱신 (자동 배포)"
        subprocess.run(["git", "commit", "-m", msg], check=True, **gk)
        push = subprocess.run(["git", "push", "origin", "main"], **gk)
        if push.returncode == 0:
            print("  → 배포 완료: GitHub push 성공 (Vercel 자동 반영 ~1-2분)")
        else:
            print(f"  → 푸시 실패(동기화는 정상): {(push.stderr or '')[-300:]}")
    except Exception as e:
        print(f"  → 배포 단계 오류(동기화는 정상): {e}")


def load_locked_markets():
    path = "locked_markets.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            locked = json.load(f)
            print(f"  [LOCK] 잠금 마켓 {len(locked)}개 보존")
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
    parser = argparse.ArgumentParser(description="폴리볼 콘텐츠 빌더 엔진 v2.6")
    parser.add_argument("--hours", type=int, default=24, help="(미사용·하위호환)")
    parser.add_argument("--no-collect", action="store_true", help="수집 단계 건너뛰기 (기존 JSON 사용)")
    parser.add_argument("--no-process", action="store_true", help="AI 생성 단계 건너뛰기")
    parser.add_argument("--max-keywords", type=int, default=20, help="생성에 쓸 키워드 최대 개수 (기본: 20)")
    parser.add_argument("--per-keyword", type=int, default=3, help="키워드당 생성 마켓 최대 개수 (기본: 3)")
    parser.add_argument("--creative", type=int, default=8, help="AI 자유 제안 마켓 개수 (기본: 8)")
    parser.add_argument("--no-push", action="store_true", help="동기화 후 git push(배포) 건너뛰기")
    parser.add_argument("--open", action="store_true", help="완료 후 대시보드 자동 열기")
    args = parser.parse_args()

    start = datetime.now()
    date_str = start.strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"폴리볼 콘텐츠 엔진 v2.6 시작: {start.strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    # 1단계: 하이브리드 키워드 수집 (도메인 시드 + 트렌드, 실제 기사 연결)
    if not args.no_collect:
        print("[ 1단계 ] 하이브리드 키워드 & 기사 수집")
        items = engine.collect_keywords()
        issues = engine.keywords_to_issues(items)
        with open("collected_issues.json", "w", encoding="utf-8") as f:
            json.dump(issues, f, ensure_ascii=False, indent=2)
        with open("collected_keywords.json", "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"→ collected_issues.json 저장 ({len(issues)}개 기사)\n")
    else:
        print("[ 1단계 ] 수집 건너뜀 (기존 데이터 사용)\n")
        with open("collected_issues.json", encoding="utf-8") as f:
            issues = json.load(f)
        items = []
        if os.path.exists("collected_keywords.json"):
            with open("collected_keywords.json", encoding="utf-8") as f:
                items = json.load(f)

    markets = []
    if not args.no_process:
        if not os.environ.get("GEMINI_API_KEY"):
            print("[경고] GEMINI_API_KEY가 없습니다. .env 파일을 확인하세요.")
            print("  → AI 생성 단계를 건너뜁니다.\n")
        else:
            print("[ 2단계 ] 콘텐츠 생성 (게이트키퍼 + 예측우선)")
            # 잠금 마켓 로드
            locked = load_locked_markets()
            locked_questions = {m.get("question", "") for m in locked}

            # 엔진: 게이트키퍼 → 키워드별 다각도 생성 + AI 자유제안 (잠금 질문 자동 제외)
            markets = engine.build_markets(
                items, locked_questions,
                max_keywords=args.max_keywords,
                per_keyword_max=args.per_keyword,
                creative_count=args.creative,
            )

            # 중복 제거 + 점수 필터 + 정렬 (기존 유틸 재사용)
            markets = deduplicate_markets(markets)
            markets = filter_and_sort(markets)

            # 잠금 마켓을 맨 앞에 붙여서 보존
            markets = locked + markets
            with open("market_drafts.json", "w", encoding="utf-8") as f:
                json.dump(markets, f, ensure_ascii=False, indent=2)
            print(f"→ market_drafts.json 저장 ({len(markets)}개)\n")
    else:
        print("[ 2단계 ] AI 생성 건너뜀\n")
        if os.path.exists("market_drafts.json"):
            with open("market_drafts.json", encoding="utf-8") as f:
                markets = json.load(f)

    # 히스토리 저장
    save_history(date_str, issues, markets)

    print("[ 3단계 ] 대시보드 생성")
    path = build_dashboard()

    # 동기화 결과를 git push → Vercel 자동 배포 (--no-push로 끌 수 있음)
    if not args.no_push:
        deploy_to_git()

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"완료! 소요시간: {elapsed}초")
    print(f"{'='*50}")

    if args.open and path:
        webbrowser.open(f"file:///{os.path.abspath(path)}")


if __name__ == "__main__":
    main()
