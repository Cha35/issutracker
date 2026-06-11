"""
폴리볼 콘텐츠 빌더 엔진 v2.6 (운영 통합 버전)
- 하이브리드 수집(도메인 시드 + 트렌드) → 워싱금지 게이트키퍼 → 예측우선 콘텐츠 생성
- 모든 콘텐츠는 실제 기사 원문 링크 + prompt_version 도장이 찍힘
- 출력은 기존 대시보드(잠금/내역/동기화) 스키마와 호환되도록 매핑
"""
import os
import json
import time
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# 판단·분석 작업은 flash-lite 지양 → pro
MODEL = "gemini-2.5-pro"

# 프롬프트 버전 (피드백 루프의 귀속 기준) — 프롬프트 수정 시 반드시 올릴 것
PROMPT_VERSION = "v4.3"


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1단계: 하이브리드 수집 (도메인 시드 메인 + 트렌드 서브)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEED_DOMAINS = {
    "스포츠":      ["KBO 프로야구", "손흥민", "K리그", "MLB"],
    "주식/재테크":  ["SK하이닉스 주가", "삼성전자 주가", "비트코인 시세", "2차전지"],
    "드라마/웹툰":  ["넷플릭스 드라마 화제", "디즈니플러스 신작", "인기 웹툰 드라마화"],
    "라이프스타일": ["갓생 루틴", "러닝 크루", "팝업스토어"],
    "직장/가치관":  ["조용한 퇴사", "MZ 직장인", "주 4일제"],
    "테크/가젯":    ["아이폰 신형", "갤럭시 신제품", "AI 챗봇"],
}
TREND_RSS = "https://trends.google.com/trending/rss?geo=KR"


def fetch_news_for_keyword(keyword, count=6):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries[:count]:
        # HTML 태그 제거 + 길이 확대 (실제 수치·맥락 확보 → 수치 환각 방지)
        raw_summary = e.get("summary", "")
        clean = BeautifulSoup(raw_summary, "html.parser").get_text(" ", strip=True)
        out.append({
            "title":   e.get("title", ""),
            "summary": clean[:400],
            "link":    e.get("link", ""),
        })
    return out


def collect_keywords(seeds_per_domain=3, trend_count=8):
    """모든 키워드는 실제 기사 원문에 연결돼야 채택됨. 뉴스는 병렬 수집."""
    from concurrent.futures import ThreadPoolExecutor

    # 1) 후보 키워드 구성 (도메인 시드 + 트렌드)
    candidates, seen = [], set()
    for domain, seeds in SEED_DOMAINS.items():
        for seed in seeds:
            if seed not in seen:
                seen.add(seed)
                candidates.append((seed, domain))
    feed = feedparser.parse(TREND_RSS)
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        if title and title not in seen:
            seen.add(title)
            candidates.append((title, "트렌드"))

    # 2) 뉴스 병렬 수집 (순차 → 동시)
    print(f"  뉴스 병렬 수집 ({len(candidates)}개 후보)...")

    def _fetch(c):
        kw, dom = c
        return {"keyword": kw, "domain": dom, "news": fetch_news_for_keyword(kw)}

    with ThreadPoolExecutor(max_workers=10) as ex:
        fetched = list(ex.map(_fetch, candidates))

    # 3) 링크 있는 것만, 도메인별/트렌드 상한 적용 (원래 순서 유지)
    collected, by_domain, trend_done = [], {}, 0
    for it in fetched:
        if not (it["news"] and any(n["link"] for n in it["news"])):
            continue
        dom = it["domain"]
        if dom == "트렌드":
            if trend_done >= trend_count:
                continue
            trend_done += 1
        else:
            c = by_domain.get(dom, 0)
            if c >= seeds_per_domain:
                continue
            by_domain[dom] = c + 1
        collected.append(it)
    print(f"  → 키워드 {len(collected)}개 수집 (도메인 {dict(by_domain)}, 트렌드 {trend_done})")
    return collected


def primary_source_link(news):
    for n in news:
        if n.get("link"):
            return n["link"]
    return ""


def keywords_to_issues(items):
    """수집된 키워드의 실제 기사를 기존 '이슈' 포맷으로 변환 (수집 내역 탭용)."""
    now_iso = datetime.now().isoformat()
    issues, seen = [], set()
    for it in items:
        for n in it["news"]:
            title = n.get("title", "").strip()
            if title and title not in seen and len(title) > 5:
                seen.add(title)
                issues.append({
                    "title": title,
                    "summary": n.get("summary", ""),
                    "link": n.get("link", ""),
                    "published": now_iso,
                    "source": f"엔진:{it['domain']}",
                    "category": it["domain"],
                })
    return issues


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2단계: 게이트키퍼 (워싱 금지 + 예측 우선, 억지 변환 금지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GATEKEEPER_SCHEMA = {
    "type": "object",
    "properties": {
        "decision":         {"type": "string", "enum": ["PASS", "FAIL"]},
        "recommended_type": {"type": "string", "enum": ["PREDICTION", "VOTE_OPINION", "SNACK_TARGET"]},
        "reason":           {"type": "string"},
    },
    "required": ["decision", "recommended_type", "reason"]
}

GATEKEEPER_PROMPT = """당신은 1030(10대 후반~30대 초중반) 타겟 예측·투표 앱 '폴리볼'의 수석 편집장입니다.
오늘은 {today}입니다. 아래 키워드와 실제 기사를 보고, 1030이 과몰입하며 댓글로 논쟁할 콘텐츠가 될지 판정하세요.

[키워드]: {keyword}
[도메인]: {domain}
[관련 기사]:
{news}

━━━ ❌ 무조건 FAIL ━━━
- 중심 주체가 '특정 정치인 개인'이거나 '정당 간 감정적/시사적 해프닝'(의원 말실수, 축하난 소동, 진영 공방)
- 잔혹 강력범죄, 재난/사건사고, 진행 중 법적 소송
- 중장년 중심 이슈 또는 유저 삶과 무관한 거시경제 절차(금리 회의록, 상장폐지 행정절차)

━━━ ⭕ PASS (워싱 금지! 민감해도 적극 통과) ━━━
정치·사회 맥락이 얽혀도 유저의 자산/일상/직장/소비콘텐츠에 직결되면 PASS.
- 드라마·웹툰발 사회논쟁(교권/학폭), 마트 의무휴업, 코인 과세, 주4일제
- 개별종목 주가 급등락, 코인 시세, 부동산 체감 / 스포츠 경기·순위·이적 / 음악·드라마·게임 / 라이프스타일·소비 / 직장 가치관·연애

━━━ ⭐ recommended_type 선택 (예측이 폴리볼의 본질! 단, 억지 변환 금지) ━━━
- 이 키워드에서 '특정 시점에 주가/경기결과/공식발표 등 명확한 Fact로 YES/NO 정산'이 **자연스럽게** 가능하면 PREDICTION을 우선 선택하세요.
- [중요·억지 변환 금지] 키워드가 태생적으로 가치관·취향·라이프스타일(갓생, 조용한 퇴사, 러닝 크루, MZ 직장인, 번아웃 등)이라서 예측으로 만들면 키워드와 겉돌거나 무리하게 비틀어야 한다면(예: '러닝 크루'를 '휠라홀딩스 주가 예측'으로, '갓생'을 '예능 시청률 예측'으로 점프), 절대 PREDICTION으로 끼워맞추지 말고 VOTE_OPINION 또는 SNACK_TARGET을 선택하세요.
- 판단 기준: "이 키워드를 보고 1030이 떠올리는 가장 자연스러운 반응이 '결과 맞히기'인가, '내 취향·생각 표현'인가?"

JSON으로만 답하세요."""


def run_gatekeeper(item):
    news_text = "\n".join(f"- {n['title']}" for n in item["news"])
    prompt = GATEKEEPER_PROMPT.format(
        today=today_str(), keyword=item["keyword"], domain=item["domain"], news=news_text)
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=GATEKEEPER_SCHEMA),
    )
    return json.loads(resp.text)


# 배치 게이트키퍼 — 전체 키워드를 1회 호출로 판정 (속도 최적화)
GATEKEEPER_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index":            {"type": "integer"},
                    "decision":         {"type": "string", "enum": ["PASS", "FAIL"]},
                    "recommended_type": {"type": "string", "enum": ["PREDICTION", "VOTE_OPINION", "SNACK_TARGET"]},
                    "reason":           {"type": "string"},
                },
                "required": ["index", "decision", "recommended_type", "reason"],
            },
        }
    },
    "required": ["results"],
}

GATEKEEPER_BATCH_PROMPT = """당신은 1030 타겟 예측·투표 앱 '폴리볼'의 수석 편집장입니다. 오늘은 {today}.
아래 키워드 목록을 각각 판정하세요. 1030이 과몰입하며 댓글로 논쟁할 콘텐츠가 될지 봅니다.

[키워드 목록]
{items}

━━━ ❌ 무조건 FAIL ━━━
- 중심 주체가 '특정 정치인 개인'이거나 '정당 간 감정적/시사적 해프닝'(의원 말실수, 축하난 소동, 진영 공방)
- 잔혹 강력범죄, 재난/사건사고, 진행 중 법적 소송
- 중장년 중심 이슈 또는 유저 삶과 무관한 거시경제 절차(금리 회의록, 상장폐지 행정절차)

━━━ ⭕ PASS (워싱 금지! 민감해도 적극 통과) ━━━
정치·사회 맥락이 얽혀도 유저의 자산/일상/직장/소비콘텐츠에 직결되면 PASS.
- 드라마·웹툰발 사회논쟁(교권/학폭), 마트 의무휴업, 코인 과세, 주4일제
- 개별종목 주가 급등락, 코인 시세, 부동산 체감 / 스포츠 경기·순위·이적 / 음악·드라마·게임 / 라이프스타일·소비 / 직장 가치관·연애

━━━ ⭐ recommended_type (예측이 본질! 단, 억지 변환 금지) ━━━
- Fact(주가/경기결과/공식발표 등 특정 시점 YES/NO 정산)가 자연스러우면 PREDICTION 우선.
- 태생적으로 가치관·취향·라이프스타일이라 예측이 억지스러우면 VOTE_OPINION 또는 SNACK_TARGET.

각 키워드의 index에 대응하는 decision/recommended_type/reason을 JSON results 배열로 출력하세요."""


def run_gatekeeper_batch(items):
    """전체 키워드를 1회 호출로 판정 → [{index, decision, recommended_type, reason}]."""
    lines = []
    for i, it in enumerate(items):
        heads = "; ".join(n.get("title", "") for n in it.get("news", [])[:3])
        lines.append(f"{i}. 키워드:{it['keyword']} | 도메인:{it.get('domain','')} | 기사:{heads}")
    prompt = GATEKEEPER_BATCH_PROMPT.format(today=today_str(), items="\n".join(lines))
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=GATEKEEPER_BATCH_SCHEMA),
    )
    return json.loads(resp.text).get("results", [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3단계: 콘텐츠 생성 (source_link / 3축점수 / 환각차단 / 예측우선)
#         키워드 1개당 다각도 마켓 1~3개 (배열)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MARKET_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "content_type":               {"type": "string", "enum": ["PREDICTION", "VOTE_OPINION", "SNACK_TARGET"]},
        "trend_tags":                 {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "target_audience":            {"type": "string"},
        "poll_question":              {"type": "string"},
        "options":                    {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
        "content_insight":            {"type": "string"},
        "audience_insight_guide":     {"type": "string"},
        "recommended_segments": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "axis":   {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["axis", "reason"],
            },
        },
        "resolution_criteria":        {"type": "string"},
        "push_notification_headline": {"type": "string"},
        "editorial_note":             {"type": "string"},
        "scores": {
            "type": "object",
            "properties": {
                "timeliness":    {"type": "integer"},
                "resolvability": {"type": "integer"},
                "shareability":  {"type": "integer"},
            },
            "required": ["timeliness", "resolvability", "shareability"]
        },
    },
    "required": ["content_type", "trend_tags", "target_audience", "poll_question", "options",
                 "content_insight", "audience_insight_guide", "recommended_segments", "resolution_criteria",
                 "push_notification_headline", "editorial_note", "scores"]
}

CONTENT_SCHEMA = {
    "type": "object",
    "properties": {"markets": {"type": "array", "items": MARKET_ITEM_SCHEMA, "minItems": 1, "maxItems": 3}},
    "required": ["markets"]
}

# 수치·날짜 공통 규칙 (grounded/creative 둘 다 사용)
NUMBER_DATE_RULES = """━━━ 🚨 날짜·수치 규칙 (반드시 준수) ━━━
- 오늘은 {today}. 과거 연도(2024 등)를 절대 쓰지 마세요.
- [날짜] '이번 주 금요일', '이번 주말 경기', '다음 달 발표', '올해 안에' 같은 상대 표현만 사용하세요. '2026-06-12' 같은 특정 날짜를 직접 계산해 쓰는 것을 금지합니다(요일·날짜 오류 위험).
- [수치 — 중요] 관련 기사에 실제 수치(현재가, 목표가, 기록, 시청률, 투자액 등)가 명시돼 있으면, 그 정확한 숫자를 마켓 질문/선택지에 적극 노출하세요. 정산 기준선도 기사의 실제 수치를 활용하면 좋습니다.
- 단, 기사에 없어서 당신이 정확한 값을 모르는 수치만 'OOO원', '△△%' 같은 플레이스홀더로 비우세요. 절대 그럴듯한 가짜 숫자를 지어내지 마세요."""

TYPE_RULES = """━━━ 유형별 고도화 규칙 ━━━
① PREDICTION — "직관·팬심으로 찍는 보상 콘텐츠" (폴리볼의 본질)
- [필수] 주가/경기결과/공식발표 등 '특정 시점에 명확한 Fact로 YES/NO 정산' 가능해야 함. resolution_criteria에 "무엇이/언제 확정되면 정답인지" 명확히 기술.
- ⭕ 예: "SK하이닉스, 이번 주 금요일 종가가 (기사 속 현재가) 선을 지킬까? [지켜낸다 vs 깨진다]"
② VOTE_OPINION — "정답 없지만 댓글창 터지는 콘텐츠"
- 투표 후 통계(%)로 논쟁이 붙는 밸런스. 얕은 호불호 금지.
- ⭕ 예: "드라마 '참교육' 화제! '교권보호 전담기관' 필요할까? [필수다 vs 인권침해 우려 vs 중립]"
③ SNACK_TARGET — "페르소나 Pain Point 저격"
- 타겟의 피로감/욕망/감성을 3~5개 보기에 날카롭게. 진부한 질문 금지.
- ⭕ 예: "퇴근 후 번아웃, 나를 살리는 힐링 처방전은? [복싱 vs 방구석 넷플릭스 vs 코노 소리지르기]"

━━━ 점수 (scores, 각 1~5) ━━━
- timeliness: 1=식은 이슈 / 3=이번 주 화제 / 5=실시간 터지는 중
- resolvability: 1=정산 불가 / 3=대략 판정 / 5=특정 날짜·공식발표로 YES/NO 확정 (VOTE/SNACK은 '결과 해석 명확성')
- shareability: 1=무반응 / 3=투표는 함 / 5=댓글창 터지고 공유각

━━━ 출력 규칙 ━━━
- target_audience: 1030 세부 세그먼트 (예: 2030 주린이, Z세대 드라마 팬)
- trend_tags: 1030이 SNS에서 쓸 법한 팝한 해시태그 최대 3개 (예: "#서학개미", "#퇴사각", "#갓생")
- content_insight: [유저 노출용 카피 — 절대 비우지 말 것] 앱 화면에서 질문 위/아래에 그대로 보여줄 2~3문장. 이 이슈가 왜 지금 핫한지 유저가 읽고 "아 그래서 화제구나, 나도 투표해야지" 싶게 만드는 흥미로운 1030 구어체. 분석·운영 메모 투(예: "~을 분석했습니다", "기획 의도는") 금지. ⭕ 예시 톤: "요즘 단톡방서 삼성전자 주가 얘기 많죠? 28만전자까지 갔다가 반등 중인데, 이번 달 향방에 개미들 눈이 쏠려 있어요."
- audience_insight_guide: [운영자용] 이 마켓 발행 후 참여자 데이터에서 [성별/연령/거주지] 중 어떤 세그먼트를 중점 분석해야 서비스 전략에 유리한지 AI 사전 가이드 1~2문장. ⭕ 예: "Y2K 트렌드라 20대 여성의 옵션별 선택률 차이를 주목하세요"
- recommended_segments: [핵심] 이 마켓을 "어떤 지표(축)로 묶어서 보면" 가장 인사이트가 큰지 우선순위 1~3개. 각 axis/reason. axis는 묶음 기준으로 '성별','연령대','지역','성별×연령','연령×지역' 중에서. reason은 "그 축으로 옵션별 선택률을 보면 무엇이 드러나는지" 한 줄. ⭕ 예: 1순위 axis=연령대 / reason="세대별 투자 낙관도 차이가 커서 20대 vs 30대 옵션 선택률 비교가 핵심", 2순위 axis=성별 / reason="남녀 리스크 선호 차이 확인"
- poll_question: 스크롤 멈추게 하는 과몰입형 구어체 / push_notification_headline: 30자 이내 / editorial_note: [운영자용] 기획 의도·가치관 치환 배경 2~3문장"""

CONTENT_PROMPT = """당신은 1030 정조준 예측·투표 앱 '폴리볼'의 콘텐츠 기획자입니다.
오늘은 {today}입니다. 유저가 인스타·숏폼·커뮤니티에서 소비하고 친구에게 공유하며 댓글로 논쟁할 콘텐츠를 만드세요.
민감한 사회·경제 이슈라도 '진영 싸움'이 아니라 '세련된 가치관 투표' 또는 '정교한 예측'으로 치환하세요.

[트렌드 키워드]: {keyword}
[관련 기사]:
{news}

위 키워드로 서로 다른 각도의 폴리볼 마켓을 {n_min}~{n_max}개 만드세요(markets 배열).
- 예측이 폴리볼의 본질이므로, 자연스럽게 가능하면 **예측형(PREDICTION)을 최소 1개 이상** 포함하세요.
- 같은 키워드라도 예측/투표/스낵 각도가 다르면 함께 담아 다양성을 확보하세요. 단, 억지로 비틀지는 마세요.
- 각 마켓은 질문·선택지가 서로 확연히 달라야 합니다(중복 금지).

{number_date_rules}

{type_rules}

JSON으로만 답하세요."""


def generate_markets_for_keyword(item, n_min=1, n_max=3):
    news_text = "\n".join(
        f"- {n['title']}" + (f" / {n['summary']}" if n['summary'] else "")
        for n in item["news"]
    )
    prompt = CONTENT_PROMPT.format(
        today=today_str(), keyword=item["keyword"], news=news_text,
        n_min=n_min, n_max=n_max,
        number_date_rules=NUMBER_DATE_RULES.format(today=today_str()),
        type_rules=TYPE_RULES,
    )
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=CONTENT_SCHEMA),
    )
    return json.loads(resp.text).get("markets", [])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3-B단계: AI 자유 제안 (creative) — 기사에 안 묶인 가정형·사회논쟁 마켓
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATIVE_PROMPT = """당신은 1030 정조준 예측·투표 앱 '폴리볼'의 크리에이티브 기획자입니다.
오늘은 {today}입니다. 아래 오늘의 트렌드 키워드를 **맥락 힌트**로만 참고하되, 특정 기사에 묶이지 않아도 됩니다.

[오늘의 트렌드 키워드]
{keywords}

현재 한국 1030이 카톡·커뮤니티에서 나눌 법한 **자유로운 가정 시나리오·사회 논쟁·트렌드 기반** 마켓을 {count}개 생성하세요(markets 배열).

[생성 방향]
- "만약 ~한다면?" 형식의 가정형 질문 환영 / 드라마·웹툰·예능의 사회 이슈를 현실에 대입 환영 / 찬반이 갈리는 논쟁 환영
- 예측형(PREDICTION)도 일부 섞되, 정산 가능한 형태(공식 발표/기록 등)일 때만. 나머지는 VOTE_OPINION·SNACK_TARGET로.
- 진영 싸움이 아닌 '가치관·라이프스타일 선택'으로 치환

[⚠️ 실제 인물/출연자 이름 환각 금지]
- 실제 방송·인물의 이름이 확실하지 않으면 절대 지어내지 말 것. "참가자 A/B", "출연자들", "당신이 응원하는 유형" 등으로 표현하거나, 완전히 가상의 설정을 쓸 것.

{number_date_rules}

{type_rules}

JSON으로만 답하세요."""

# creative도 배열 maxItems를 작게(3) 유지 — 큰 배열은 Gemini 스키마 상태수 초과
CREATIVE_BATCH = 3


def _generate_creative_batch(keywords, batch_size, avoid_questions):
    avoid = ""
    if avoid_questions:
        sample = list(avoid_questions)[-8:]
        avoid = "\n[이미 만든 질문 — 중복 금지]\n" + "\n".join(f"- {q}" for q in sample)
    prompt = CREATIVE_PROMPT.format(
        today=today_str(), keywords=keywords, count=batch_size,
        number_date_rules=NUMBER_DATE_RULES.format(today=today_str()),
        type_rules=TYPE_RULES,
    ) + avoid
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=CONTENT_SCHEMA),  # maxItems 3 재사용
    )
    return json.loads(resp.text).get("markets", [])


def generate_creative_markets(items, count=8):
    """배치(3개)로 끊어서 count개까지 생성. 중복 질문 회피."""
    keywords = "\n".join(f"- [{it['domain']}] {it['keyword']}" for it in items[:24])
    out, seen = [], set()
    remaining = count
    while remaining > 0:
        batch_size = min(CREATIVE_BATCH, remaining)
        try:
            batch = _generate_creative_batch(keywords, batch_size, seen)
        except Exception as e:
            print(f"    [creative 배치 오류] {e}")
            break
        added = 0
        for m in batch:
            q = m.get("poll_question", "")
            if q and q not in seen:
                seen.add(q)
                out.append(m)
                added += 1
        remaining -= max(added, batch_size)  # 진전 없으면 무한루프 방지
        if added == 0:
            break
        time.sleep(1)
    return out


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 대시보드 스키마로 매핑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CT_TO_MARKET_TYPE = {
    "PREDICTION":   "prediction",
    "VOTE_OPINION": "vote",
    "SNACK_TARGET": "snack",
}


def to_market(raw, keyword, domain, source_link, source_type="engine"):
    """v2.6 생성 결과 → 대시보드 호환 마켓 dict (+ 신규 필드 + prompt_version)."""
    scores = raw.get("scores", {})
    total = scores.get("timeliness", 0) + scores.get("resolvability", 0) + scores.get("shareability", 0)
    score5 = max(1, min(5, round(total / 3)))  # 3~15 → 1~5

    return {
        # ── 대시보드 호환 필드 ──
        "issue_title":          keyword,
        "market_type":          CT_TO_MARKET_TYPE.get(raw.get("content_type"), "vote"),
        "question":             raw.get("poll_question", ""),
        "options":              raw.get("options", []),
        "category":             domain,
        "rationale":            raw.get("editorial_note", ""),
        "target_audience":      raw.get("target_audience", "공통"),
        "marketability_score":  score5,
        "source_link":          source_link,
        "source_type":          source_type,
        # ── 신규 보존 필드 (피드백 루프/추후 활용) ──
        "content_type":         raw.get("content_type"),
        "keyword":              keyword,
        "trend_tags":           raw.get("trend_tags", []),
        "content_insight":      raw.get("content_insight", ""),
        "audience_insight_guide": raw.get("audience_insight_guide", ""),
        "recommended_segments": raw.get("recommended_segments", []),
        "resolution_criteria":  raw.get("resolution_criteria", ""),
        "push_notification_headline": raw.get("push_notification_headline", ""),
        "scores":               scores,
        "total_score":          total,
        "prompt_version":       PROMPT_VERSION,
        "generated_at":         datetime.now().isoformat(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 오케스트레이션
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 수동 발행: google_search 실시간 조사 → 구조화 (2단계)
#   (google_search 그라운딩 + response_schema는 동시 사용 불가 → 분리)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH_PROMPT = """오늘은 {today}입니다. 키워드 '{keyword}'에 대해 지금 한국에서 화제가 되는 최신 사실/뉴스/수치를 구글 검색으로 조사하세요.
- 핵심 사실, 관련 날짜, 구체적 수치(주가/기록/통계 등)를 불릿으로 정리
- 1030(10대 후반~30대 초중반) 관점에서 흥미롭거나 논쟁이 될 포인트도 포함
- 추측이 아닌 검색으로 확인된 사실 위주로"""


def _extract_grounding_link(resp):
    """google_search 그라운딩 응답에서 대표 출처 URL 추출."""
    try:
        gm = resp.candidates[0].grounding_metadata
        for ch in (gm.grounding_chunks or []):
            if ch.web and ch.web.uri:
                return ch.web.uri
    except Exception:
        pass
    return ""


def generate_from_manual_keyword(keyword, n_max=3):
    """관리자 수동 키워드 → 실시간 웹조사 → v4.0 마켓 (대시보드 호환)."""
    # 1단계: google_search 그라운딩으로 실시간 조사
    search_tool = types.Tool(google_search=types.GoogleSearch())
    research = client.models.generate_content(
        model=MODEL,
        contents=RESEARCH_PROMPT.format(today=today_str(), keyword=keyword),
        config=types.GenerateContentConfig(tools=[search_tool]),
    )
    research_text = (research.text or "").strip()
    src = _extract_grounding_link(research)
    if not research_text:
        research_text = f"(검색 결과 없음) 키워드: {keyword}"

    # 2단계: 조사 결과를 response_schema로 구조화
    prompt = CONTENT_PROMPT.format(
        today=today_str(), keyword=keyword, news=research_text,
        n_min=1, n_max=n_max,
        number_date_rules=NUMBER_DATE_RULES.format(today=today_str()),
        type_rules=TYPE_RULES,
    )
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=CONTENT_SCHEMA),
    )
    raws = json.loads(resp.text).get("markets", [])
    return [to_market(raw, keyword, "수동검색", src, "manual") for raw in raws]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 참여자 특성 분석 리포트 (버튼 클릭 시에만 호출)
#   집계된 참여자 통계 → Gemini 해석 텍스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PARTICIPANT_INSIGHT_SCHEMA = {
    "type": "object",
    "properties": {"insight": {"type": "string"}},
    "required": ["insight"],
}

PARTICIPANT_INSIGHT_PROMPT = """당신은 1030 예측·투표 앱 '폴리볼'의 데이터 분석가입니다.
아래 마켓에 실제 참여한 유저들의 집계 통계입니다. 이 데이터를 해석해 '참여자 특성 분석 리포트'를 작성하세요.

[마켓 질문]: {question}
[선택지]: {options}
[참여자 통계]
- 총 참여: {total}명
- 성별: {gender}
- 연령대: {age}
- 지역: {region}
{guide}

[작성 규칙]
- 어떤 세그먼트가 특히 활발히/특이하게 참여했는지, 서비스 전략(타겟팅·콘텐츠 방향)에 주는 시사점을 2~4문장으로.
- 통계 숫자에 근거할 것. 데이터에 없는 내용 지어내기 금지.
- 운영자가 바로 읽고 의사결정에 쓸 수 있는 톤.

JSON으로만 답하세요."""


def generate_participant_insight(question, options, stats, guide=""):
    g = f"[AI 사전 관전 가이드]: {guide}" if guide else ""
    prompt = PARTICIPANT_INSIGHT_PROMPT.format(
        question=question,
        options=", ".join(options or []),
        total=stats.get("total", 0),
        gender=stats.get("gender", {}),
        age=stats.get("age", {}),
        region=stats.get("region", {}),
        guide=g,
    )
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=PARTICIPANT_INSIGHT_SCHEMA),
    )
    return json.loads(resp.text).get("insight", "")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 거절 패턴 분석 (버튼 클릭 시에만 호출 — 자동 API 사용 안 함)
#   결과는 관리자 검토용 제안. 프롬프트 자동 수정 ❌
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REJECT_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "diagnosis":           {"type": "string"},
        "top_issues":          {"type": "array", "items": {"type": "string"}},
        "prompt_improvements": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["diagnosis", "top_issues", "prompt_improvements"],
}

REJECT_ANALYSIS_PROMPT = """당신은 1030 예측·투표 앱 '폴리볼' 콘텐츠 엔진(현재 프롬프트 버전 {version})의 프롬프트 엔지니어입니다.
오늘은 {today}. 아래는 관리자가 '제외(거절)'한 마켓과 그 사유 목록입니다. 이 패턴을 분석하세요.

[제외된 마켓 목록]
{items}

다음을 JSON으로 출력하세요. (자동 적용이 아니라 관리자 검토용 제안입니다)
- diagnosis: 현재 생성 프롬프트가 반복적으로 어떤 잘못된 콘텐츠를 만들고 있는지 2~4문장 진단
- top_issues: 가장 빈번하거나 치명적인 문제 패턴 3~5개 (각 한 줄)
- prompt_improvements: 생성 프롬프트에 '그대로 추가'하면 좋을 구체적 규칙 또는 "❌ 나쁜 예시" 문장들 (복붙 가능한 형태로 3~6개)"""


def analyze_rejections(rejects):
    """누적된 거절 사유를 1회 분석 → 진단 + 프롬프트 개선 제안 (검토용)."""
    if not rejects:
        return None
    lines = []
    for r in rejects[:60]:
        reasons = ", ".join(r.get("rejected_reasons", []) or [])
        memo = r.get("rejected_memo", "") or ""
        ctype = r.get("content_type") or r.get("market_type", "")
        lines.append(f"- [{ctype}] 질문:{r.get('question','')} / 사유:{reasons}" + (f" / 메모:{memo}" if memo else ""))
    prompt = REJECT_ANALYSIS_PROMPT.format(
        today=today_str(), version=PROMPT_VERSION, items="\n".join(lines))
    resp = client.models.generate_content(
        model=MODEL, contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=REJECT_ANALYSIS_SCHEMA),
    )
    return json.loads(resp.text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 백필: content_insight 비어있는 기존 마켓 채우기 (유저 노출용 카피)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSIGHT_BACKFILL_SCHEMA = {
    "type": "object",
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "content_insight": {"type": "string"},
                },
                "required": ["index", "content_insight"],
            },
        }
    },
    "required": ["insights"],
}

INSIGHT_BACKFILL_PROMPT = """당신은 1030 예측·투표 앱 '폴리볼'의 콘텐츠 에디터입니다. 오늘은 {today}.
아래 각 마켓에 대해, 앱 화면에서 유저에게 그대로 노출할 'content_insight'를 작성하세요.

[content_insight 규칙]
- 이 이슈가 왜 지금 핫한지 유저가 읽고 "아 그래서 화제구나, 투표해야지" 싶게 만드는 흥미로운 1030 구어체 2~3문장.
- 분석·운영 메모 투 금지("~분석했습니다", "기획 의도" 등). 유저에게 말 거는 톤.
- 모르는 수치는 지어내지 말 것.

[마켓 목록]
{items}

각 index에 대응하는 content_insight를 JSON으로 출력하세요."""


def backfill_insights(markets, batch_size=8):
    """content_insight가 비어있는 마켓을 골라 유저 노출용 카피로 채움 (in-place)."""
    targets = [(i, m) for i, m in enumerate(markets) if not (m.get("content_insight") or "").strip()]
    if not targets:
        return 0
    filled = 0
    for b in range(0, len(targets), batch_size):
        chunk = targets[b:b + batch_size]
        listing = "\n".join(
            f"{i}. [{m.get('content_type') or m.get('market_type','')}] 키워드:{m.get('keyword','')} / 질문:{m.get('question','')}"
            for i, m in chunk
        )
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=INSIGHT_BACKFILL_PROMPT.format(today=today_str(), items=listing),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=INSIGHT_BACKFILL_SCHEMA),
            )
            for row in json.loads(resp.text).get("insights", []):
                idx = row.get("index")
                ci = (row.get("content_insight") or "").strip()
                if isinstance(idx, int) and 0 <= idx < len(markets) and ci:
                    markets[idx]["content_insight"] = ci
                    filled += 1
        except Exception as e:
            print(f"  [insight 백필 오류] {e}")
        time.sleep(1)
    return filled


def build_markets(items, locked_questions=None, max_keywords=20,
                  per_keyword_max=3, creative_count=8, max_workers=8):
    """게이트키퍼(배치) → 키워드별 다각도 생성(병렬) + AI 자유제안 → 대시보드 마켓 리스트."""
    from concurrent.futures import ThreadPoolExecutor

    locked_questions = locked_questions or set()
    seen_questions = set(locked_questions)
    markets = []

    # 1) 게이트키퍼 — 전체 키워드 1회 배치 판정 (순차 26콜 → 1콜)
    print("  [게이트키퍼] 배치 판정...")
    passed = []
    try:
        results = run_gatekeeper_batch(items)
        by_idx = {r.get("index"): r for r in results}
        for i, it in enumerate(items):
            r = by_idx.get(i)
            if not r:
                continue
            if r.get("decision") == "PASS":
                it["recommended_type"] = r.get("recommended_type", "PREDICTION")
                passed.append(it)
            print(f"    {r.get('decision')} [{r.get('recommended_type','-'):<12}] {it['keyword'][:16]} | {(r.get('reason') or '')[:28]}")
    except Exception as e:
        print(f"    [배치 게이트키퍼 오류] {e} → 개별 판정으로 폴백")
        for it in items:
            try:
                res = run_gatekeeper(it)
                if res["decision"] == "PASS":
                    it["recommended_type"] = res.get("recommended_type", "PREDICTION")
                    passed.append(it)
            except Exception:
                pass

    passed.sort(key=lambda x: 0 if x.get("recommended_type") == "PREDICTION" else 1)
    n_pred = sum(1 for p in passed if p.get("recommended_type") == "PREDICTION")
    print(f"  → {len(items)}개 중 {len(passed)}개 통과 (예측형 추천 {n_pred}개)")

    # 2) 키워드별 다각도 마켓 — 병렬 생성 (순차 20콜 → 동시 실행)
    targets = passed[:max_keywords]
    print(f"  [생성] 키워드 {len(targets)}개 × 최대 {per_keyword_max}개 병렬 생성 (워커 {max_workers})...")

    def _gen(it):
        try:
            return (it, generate_markets_for_keyword(it, n_min=1, n_max=per_keyword_max))
        except Exception as e:
            print(f"    [오류] {it['keyword']}: {e}")
            return (it, [])

    def _gen_creative():
        if creative_count <= 0:
            return []
        try:
            return generate_creative_markets(items, count=creative_count)
        except Exception as e:
            print(f"    [오류] creative: {e}")
            return []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        gen_futures = [ex.submit(_gen, it) for it in targets]
        creative_future = ex.submit(_gen_creative)

        # 키워드 마켓 수집 (메인 스레드에서 dedup)
        for fut in gen_futures:
            it, raws = fut.result()
            link = primary_source_link(it.get("news", []))
            for raw in raws:
                m = to_market(raw, it["keyword"], it.get("domain", ""), link, "engine")
                if m["question"] in seen_questions:
                    continue
                seen_questions.add(m["question"])
                markets.append(m)

        # AI 자유 제안 수집
        for raw in creative_future.result():
            m = to_market(raw, raw.get("keyword", "AI 자유 제안"), "AI 자유제안", "", "creative")
            if m["question"] in seen_questions:
                continue
            seen_questions.add(m["question"])
            markets.append(m)

    print(f"  → 총 {len(markets)}개 마켓 생성")
    return markets


if __name__ == "__main__":
    # 단독 실행 테스트
    items = collect_keywords()
    markets = build_markets(items)
    print(f"\n총 {len(markets)}개 마켓 생성 (prompt_version={PROMPT_VERSION})")
    with open("market_drafts.json", "w", encoding="utf-8") as f:
        json.dump(markets, f, ensure_ascii=False, indent=2)
