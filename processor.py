from google import genai
import json
import os
from difflib import SequenceMatcher
from dotenv import load_dotenv
from config import CATEGORY_LABELS

load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """당신은 폴리볼(Polyball) 서비스의 마켓 기획자입니다.
폴리볼은 2030 남녀가 즐기는 예측·투표 플랫폼입니다.

수집된 이슈를 바탕으로 아래 5가지 마켓 유형 중 가장 적합한 유형으로 마켓 초안을 생성하세요.

마켓 유형 정의:
1. prediction (예측): 외부 결과로 정답이 확정되는 질문. 예) "손흥민, 다음 경기 득점할까?"
2. vote (투표): 유저 의견을 집계하는 질문, 외부 정답 없음. 예) "촉법소년 연령 하향해야 할까?"
3. ranking (랭킹 예측): n명/n개 중 1등을 맞히는 구조. 예) "올해 연말 시상식 대상 수상자는?"
4. numeric (수치 예측): 숫자 범위를 고르는 구조. 예) "이번 시즌 손흥민 골 수는? (0~5 / 6~10 / 11+)"
5. timing (타이밍 예측): '언제' 일어날지를 예측. 예) "BTS 완전체 컴백, 올해 안에? (Q1~Q4 / 내년 이후)"

[이슈 선별 기준 - 반드시 준수]
아래 조건에 해당하는 이슈는 마켓 생성 없이 건너뛰세요:
- 이미 결과가 확정된 경기, 시상식, 투표 결과 등 과거 사실 보도
- 단순 과거 기록/통계 회고 기사 (예: "시즌 최종 성적", "역대 기록 경신")
- 결과가 이미 알려진 사건 사고
- 정치적으로 극도로 민감하거나 혐오를 조장할 수 있는 이슈

아래 조건의 이슈를 우선 선택하세요:
- 앞으로 일어날 경기, 공연, 발표, 이벤트 관련
- 현재 진행 중인 논란, 경쟁, 시즌
- 아직 결과가 나오지 않은 선발, 계약, 이적 등
- 2030 남녀가 실제로 관심 갖고 참여할 만한 시의성 있는 주제

출력 형식은 반드시 JSON 배열로만 응답하세요. 설명 텍스트 없이 JSON만 출력하세요.
"""

USER_PROMPT_TEMPLATE = """오늘 날짜 기준으로 수집된 이슈 목록입니다. 아래 이슈들을 분석하여 폴리볼 마켓 초안을 생성해주세요.

[중요] 이미 결과가 나온 이슈, 과거 기록 회고성 기사는 반드시 건너뛰세요.
현재 시점에서 예측·투표할 수 있는 시의성 있는 이슈만 선택하세요.
각 이슈당 1~2개의 마켓을 제안하되, 2030 남녀가 참여할 만한 흥미로운 질문을 만들어주세요.

이슈 목록:
{issues}

JSON 출력 형식:
[
  {{
    "issue_title": "원본 이슈 제목",
    "market_type": "prediction|vote|ranking|numeric|timing",
    "question": "마켓 질문 (구어체, 흥미롭게)",
    "options": ["선택지1", "선택지2", ...],
    "category": "카테고리명",
    "rationale": "이 마켓 유형을 선택한 이유 (한 문장)",
    "target_audience": "주 타겟 (예: 2030 여성, 2030 남성, 공통)",
    "marketability_score": 4
  }}
]
(marketability_score는 1~5 정수로, 5가 가장 마켓화 가치가 높음. 시의성·참여도·명확성을 고려해 실제 점수를 부여하세요.)
"""


def build_issue_text(issues):
    lines = []
    for i, issue in enumerate(issues, 1):
        category = CATEGORY_LABELS.get(issue.get("category", ""), issue.get("category", ""))
        lines.append(f"{i}. [{category}] {issue['title']}")
        if issue.get("summary"):
            lines.append(f"   요약: {issue['summary'][:150]}")
    return "\n".join(lines)


def process_batch(issues, batch_size=15):
    all_markets = []

    for i in range(0, len(issues), batch_size):
        batch = issues[i:i + batch_size]
        print(f"  배치 {i // batch_size + 1} 처리 중 ({len(batch)}개 이슈)...")

        issue_text = build_issue_text(batch)
        prompt = SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE.format(issues=issue_text)

        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            markets = json.loads(raw)
            all_markets.extend(markets)
            print(f"    → {len(markets)}개 마켓 초안 생성")
        except Exception as e:
            print(f"    [오류] {e}")

    return all_markets


def enrich_with_links(markets, issues):
    """퍼지 매칭으로 이슈 링크를 마켓 초안에 추가"""
    def best_match_link(query, issue_list):
        best_score = 0
        best_link = ""
        for issue in issue_list:
            score = SequenceMatcher(None, query, issue["title"]).ratio()
            if score > best_score:
                best_score = score
                best_link = issue.get("link", "")
        return best_link if best_score >= 0.5 else ""

    for market in markets:
        title = market.get("issue_title", "")
        market["source_link"] = best_match_link(title, issues)
    return markets


def deduplicate_markets(markets, threshold=0.72):
    """질문 유사도 기반 중복 마켓 제거"""
    unique = []
    for market in markets:
        question = market.get("question", "")
        is_dup = False
        for existing in unique:
            score = SequenceMatcher(None, question, existing.get("question", "")).ratio()
            if score >= threshold:
                # 점수 높은 쪽 유지
                if market.get("marketability_score", 0) > existing.get("marketability_score", 0):
                    unique.remove(existing)
                    unique.append(market)
                is_dup = True
                break
        if not is_dup:
            unique.append(market)
    removed = len(markets) - len(unique)
    if removed > 0:
        print(f"    → 유사 마켓 {removed}개 제거 (중복 제거 후 {len(unique)}개)")
    return unique


CREATIVE_PROMPT_TEMPLATE = """당신은 폴리볼(Polyball) 서비스의 크리에이티브 마켓 기획자입니다.
폴리볼은 2030 남녀가 즐기는 예측·투표 플랫폼입니다.

아래는 오늘 수집된 이슈 키워드입니다. 이걸 **맥락 힌트**로만 참고하되,
반드시 이 기사에 묶이지 않아도 됩니다.

[오늘의 이슈 키워드]
{keywords}

[요청]
현재 한국 2030 남녀가 관심 가질 만한 **자유로운 가상 시나리오, 사회 논쟁, 트렌드 기반** 마켓 초안을 {count}개 생성하세요.

[생성 방향]
- 실제 기사가 없어도 됨. 사회 현상·문화 트렌드·가상 시나리오 기반 OK
- "만약 ~한다면?" 형식의 가정적 질문 환영
- 드라마/웹툰/예능에서 다루는 사회 이슈를 현실에 대입하는 방식 환영
- 찬반이 갈리는 논쟁 주제 환영 (vote 유형)
- 2030이 카카오톡에서 나눌 법한 주제여야 함
- 민감하거나 혐오적인 내용 제외

[⚠️ 실제 인물/출연자 이름 사용 규칙 - 반드시 준수]
- 실제 방송 프로그램(솔로지옥, 하트시그널 등)을 언급할 경우, 해당 시즌에 실제 출연한 것이 **확실하게 알려진** 인물 이름만 사용할 것
- 출연자 이름이 기억나지 않거나 불확실하다면 → 이름 대신 "참가자 A/B", "출연자들"로 표현하거나, 아예 특정 프로그램명을 언급하지 말 것
- 절대로 그럴듯해 보이는 한국 이름을 임의로 지어내지 말 것 (예: "지우&태준", "민서&도윤" 등 가상 이름 금지)
- 실제 인물이 확실하지 않으면 → 질문/선택지를 "이번 시즌 최고 커플은?", "당신이 응원하는 유형은?" 등 인물 이름 없이 구성할 것
- 완전히 가상의 프로그램을 설정해도 됨 (예: "가상의 데이팅쇼 '썸씽' 참가자 중...")

[마켓 유형]
1. prediction: 외부 결과로 정답이 확정. 예) "손흥민, 다음 경기 득점할까?"
2. vote: 유저 의견 집계, 정답 없음. 예) "교권보호국, 설치되어야 할까?"
3. ranking: n개 중 1등 맞히기
4. numeric: 숫자 범위 선택
5. timing: 언제 일어날지 예측

JSON 배열로만 응답하세요. 설명 없이 JSON만 출력하세요.

[출력 형식]
[
  {{
    "issue_title": "영감을 준 트렌드/주제 (기사 제목 아니어도 됨)",
    "market_type": "vote",
    "question": "마켓 질문 (구어체, 흥미롭게)",
    "options": ["선택지1", "선택지2", "선택지3"],
    "category": "카테고리",
    "rationale": "이 마켓을 제안한 이유",
    "target_audience": "2030 남성 또는 2030 여성 또는 공통",
    "marketability_score": 4,
    "source_type": "creative"
  }}
]
(marketability_score는 1~5 실제 점수 부여. source_type은 반드시 "creative"로 고정)
"""


def generate_creative_markets(issues, count=15):
    """수집 이슈를 힌트로 AI 자유 마켓 생성"""
    print(f"  창의적 마켓 생성 중 ({count}개 목표)...")

    # 오늘 이슈에서 키워드 추출 (제목만)
    keywords = "\n".join(
        f"- [{CATEGORY_LABELS.get(i.get('category',''), i.get('category',''))}] {i['title'][:50]}"
        for i in issues[:30]
    )
    prompt = CREATIVE_PROMPT_TEMPLATE.format(keywords=keywords, count=count)

    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        markets = json.loads(raw)
        # source_type 보정
        for m in markets:
            m["source_type"] = "creative"
            m["source_link"] = ""
        print(f"    → {len(markets)}개 자유 마켓 생성")
        return markets
    except Exception as e:
        print(f"    [오류] {e}")
        return []


def filter_and_sort(markets, min_score=3):
    filtered = [m for m in markets if m.get("marketability_score", 0) >= min_score]
    filtered.sort(key=lambda x: x.get("marketability_score", 0), reverse=True)
    return filtered


if __name__ == "__main__":
    with open("collected_issues.json", encoding="utf-8") as f:
        issues = json.load(f)

    print(f"총 {len(issues)}개 이슈 처리 시작...")
    markets = process_batch(issues)
    markets = filter_and_sort(markets)

    with open("market_drafts.json", "w", encoding="utf-8") as f:
        json.dump(markets, f, ensure_ascii=False, indent=2)

    print(f"\n마켓 초안 {len(markets)}개 생성 완료 → market_drafts.json")
