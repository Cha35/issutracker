import json
import os
from datetime import datetime
from collections import Counter
from config import CATEGORY_LABELS

MARKET_TYPE_KO = {
    "prediction": "예측",
    "vote": "투표",
    "snack": "스낵",
    "ranking": "랭킹 예측",
    "numeric": "수치 예측",
    "timing": "타이밍 예측",
}

MARKET_TYPE_COLOR = {
    "prediction": "#4F46E5",
    "vote": "#059669",
    "snack": "#DB2777",
    "ranking": "#D97706",
    "numeric": "#DC2626",
    "timing": "#7C3AED",
}

TARGET_COLOR = {
    "2030 여성": "#EC4899",
    "2030 남성": "#3B82F6",
    "공통": "#6B7280",
}


def load_data():
    issues = []
    markets = []
    if os.path.exists("collected_issues.json"):
        with open("collected_issues.json", encoding="utf-8") as f:
            issues = json.load(f)
    if os.path.exists("market_drafts.json"):
        with open("market_drafts.json", encoding="utf-8") as f:
            markets = json.load(f)
    return issues, markets


def load_history():
    history = {}
    if not os.path.exists("history"):
        return history
    dates = set()
    for fname in os.listdir("history"):
        if fname.endswith("_issues.json"):
            dates.add(fname.replace("_issues.json", ""))
    for date_str in sorted(dates, reverse=True):
        issues_path = f"history/{date_str}_issues.json"
        markets_path = f"history/{date_str}_markets.json"
        issues_data, markets_data = [], []
        if os.path.exists(issues_path):
            with open(issues_path, encoding="utf-8") as f:
                issues_data = json.load(f)
        if os.path.exists(markets_path):
            with open(markets_path, encoding="utf-8") as f:
                markets_data = json.load(f)
        history[date_str] = {"issues": issues_data, "markets": markets_data}
    return history


def render_market_card(m, idx):
    mtype = m.get("market_type", "prediction")
    color = MARKET_TYPE_COLOR.get(mtype, "#6B7280")
    type_ko = MARKET_TYPE_KO.get(mtype, mtype)
    score = m.get("marketability_score", 0)
    target = m.get("target_audience", "공통")
    target_color = TARGET_COLOR.get(target, "#6B7280")
    options_html = "".join(f'<span class="option-chip">{o}</span>' for o in m.get("options", []))
    stars = "★" * score + "☆" * (5 - score)
    source_link = m.get("source_link", "")
    issue_title = m.get("issue_title", "")
    short_title = issue_title[:55] + ("..." if len(issue_title) > 55 else "")
    source_type = m.get("source_type", "issue")
    is_creative = source_type == "creative"

    link_html = (
        f'<a href="{source_link}" target="_blank" class="source-link">📎 원문 보기</a>'
        if source_link else (
            '<span class="creative-badge">✨ AI 자유 제안</span>'
            if is_creative else '<span class="source-link-none">출처 없음</span>'
        )
    )

    # 마켓 데이터를 data 속성으로 저장 (잠금용)
    q_escaped = m.get("question", "").replace('"', '&quot;').replace("'", "&#39;")

    question = m.get('question', '').replace('<', '&lt;').replace('>', '&gt;')
    # 카드 하단 블러브: 유저 노출용 content_insight 우선, 없으면 기획의도(rationale)로 폴백
    insight_src = m.get('content_insight') or m.get('rationale', '')
    rationale = insight_src.replace('<', '&lt;').replace('>', '&gt;')
    has_insight = bool((m.get('content_insight') or '').strip())
    blurb_class = "insight-blurb" if has_insight else "rationale"
    title_attr = issue_title.replace('"', '&quot;')

    # 검색용 텍스트 (키워드 + 질문 + 원본제목 + 태그)
    search_text = " ".join([
        m.get("keyword", ""), m.get("question", ""), issue_title,
        " ".join(m.get("trend_tags", [])),
    ]).lower().replace('"', '&quot;')

    return f"""
    <div class="market-card" data-type="{mtype}" data-score="{score}" data-sourcetype="{source_type}" data-search="{search_text}" data-idx="{idx}" id="mcard-{idx}">
      <div class="locked-ribbon">🔒 잠금</div>
      <div class="card-header" style="border-left: 4px solid {color}">
        <span class="type-badge" style="background:{color}">{type_ko}</span>
        <span class="target-badge" style="background:{target_color}">{target}</span>
        <span class="score">{stars}</span>
        <button class="lock-btn" onclick="toggleLock({idx}, this)" title="잠금 시 동기화해도 유지됨">🔓</button>
        <button class="reject-btn" onclick="openRejectModal({idx})" title="이 마켓 제외 (사유 입력)">✕</button>
      </div>
      <div class="card-body" onclick="openDetailModal({idx})" title="클릭하면 상세 검수 / 발행">
        <p class="question">{question}</p>
        <div class="options">{options_html}</div>
        <div class="source-row">
          <span class="source-title" title="{title_attr}">{short_title}</span>
          {link_html}
        </div>
        <p class="{blurb_class}">{rationale}</p>
      </div>
    </div>"""


def generate_html(issues, markets, history):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    category_counts = Counter(CATEGORY_LABELS.get(i["category"], i["category"]) for i in issues)
    type_counts = Counter(m.get("market_type", "unknown") for m in markets)
    target_counts = Counter(m.get("target_audience", "공통") for m in markets)
    avg_score = sum(m.get("marketability_score", 0) for m in markets) / len(markets) if markets else 0

    category_bars = ""
    max_cat = max(category_counts.values(), default=1)
    for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = int(cnt / max_cat * 100)
        category_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{cat}</span>
          <div class="bar-bg"><div class="bar-fill" style="width:{pct}%">{cnt}</div></div>
        </div>"""

    type_pills = "".join(
        f'<span class="stat-pill" style="background:{MARKET_TYPE_COLOR.get(t,"#6B7280")}">{MARKET_TYPE_KO.get(t,t)} {cnt}개</span>'
        for t, cnt in type_counts.items()
    )
    target_pills = "".join(
        f'<span class="stat-pill" style="background:{TARGET_COLOR.get(tgt,"#6B7280")}">{tgt} {cnt}개</span>'
        for tgt, cnt in target_counts.items()
    )

    filter_buttons = '<button class="filter-btn active" onclick="filterCards(\'all\', this)">전체</button>'
    for mtype, ko in MARKET_TYPE_KO.items():
        color = MARKET_TYPE_COLOR[mtype]
        filter_buttons += f'<button class="filter-btn" style="--fc:{color}" onclick="filterCards(\'{mtype}\', this)">{ko}</button>'
    filter_buttons += '<button class="filter-btn" style="--fc:#7C3AED" onclick="filterCreative(this)">✨ AI 자유 제안</button>'
    filter_buttons += '<button class="filter-btn lock-filter-btn" style="--fc:#F59E0B" onclick="filterLocked(this)">🔒 잠금됨</button>'

    market_cards = "".join(render_market_card(m, i) for i, m in enumerate(markets))

    # 히스토리 데이터를 Python에서 JSON으로 직렬화
    history_for_js = {}
    for d, data in history.items():
        history_for_js[d] = {
            "issues": [
                {
                    "title": i.get("title", ""),
                    "category": CATEGORY_LABELS.get(i.get("category", ""), i.get("category", "")),
                    "link": i.get("link", ""),
                }
                for i in data["issues"]
            ],
            "markets": [
                {
                    "issue_title": m.get("issue_title", ""),
                    "market_type": m.get("market_type", ""),
                    "question": m.get("question", ""),
                    "source_link": m.get("source_link", ""),
                    "marketability_score": m.get("marketability_score", 0),
                    "source_type": m.get("source_type", "issue"),
                }
                for m in data["markets"]
            ],
        }

    # 현재 마켓 데이터 (잠금 저장 + 상세 검수 모달용)
    markets_for_js = [
        {
            "issue_title": m.get("issue_title", ""),
            "market_type": m.get("market_type", ""),
            "content_type": m.get("content_type", ""),
            "keyword": m.get("keyword", m.get("issue_title", "")),
            "question": m.get("question", ""),
            "options": m.get("options", []),
            "category": m.get("category", ""),
            "rationale": m.get("rationale", ""),
            "target_audience": m.get("target_audience", "공통"),
            "marketability_score": m.get("marketability_score", 0),
            "source_link": m.get("source_link", ""),
            "source_type": m.get("source_type", "issue"),
            "trend_tags": m.get("trend_tags", []),
            "content_insight": m.get("content_insight", ""),
            "audience_insight_guide": m.get("audience_insight_guide", ""),
            "recommended_segments": m.get("recommended_segments", []),
            "resolution_criteria": m.get("resolution_criteria", ""),
            "push_notification_headline": m.get("push_notification_headline", ""),
            "scores": m.get("scores", {}),
        }
        for m in markets
    ]

    # 실시간 자동 키워드 (수집 내역 탭용)
    auto_keywords = []
    if os.path.exists("collected_keywords.json"):
        try:
            with open("collected_keywords.json", encoding="utf-8") as f:
                kw_items = json.load(f)
            auto_keywords = [{"keyword": it.get("keyword", ""), "domain": it.get("domain", "")} for it in kw_items]
        except Exception:
            auto_keywords = []

    # 거절(제외) 이력 (제외 이력 탭용 — 빌드 시점 스냅샷, 로컬에선 런타임 fetch로 갱신)
    rejects_snapshot = []
    if os.path.exists("rejected_markets.json"):
        try:
            with open("rejected_markets.json", encoding="utf-8") as f:
                rejects_snapshot = json.load(f)
        except Exception:
            rejects_snapshot = []

    # 발행(진행중) 마켓 질문 집합 — 상세 모달 참여자 섹션 상태 판정용
    published_questions = []
    if os.path.exists("published_markets.json"):
        try:
            with open("published_markets.json", encoding="utf-8") as f:
                published_questions = [p.get("question", "") for p in json.load(f) if p.get("question")]
        except Exception:
            published_questions = []

    history_data_js = json.dumps(history_for_js, ensure_ascii=False)
    markets_data_js = json.dumps(markets_for_js, ensure_ascii=False)
    auto_keywords_js = json.dumps(auto_keywords, ensure_ascii=False)
    rejects_data_js = json.dumps(rejects_snapshot, ensure_ascii=False)
    published_q_js = json.dumps(published_questions, ensure_ascii=False)
    type_color_js = json.dumps(MARKET_TYPE_COLOR)
    type_ko_js = json.dumps(MARKET_TYPE_KO, ensure_ascii=False)
    history_dates = list(history_for_js.keys())
    history_date_options = "".join(
        f'<option value="{d}">{d} (이슈 {len(history_for_js[d]["issues"])}개 / 마켓 {len(history_for_js[d]["markets"])}개)</option>'
        for d in history_dates
    )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>폴리볼 이슈 수집 대시보드</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans KR', sans-serif; background: #F1F5F9; color: #1E293B; min-height: 100vh; }}
  header {{ background: white; padding: 0 32px; border-bottom: 1px solid #E2E8F0; display: flex; align-items: center; gap: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); position: sticky; top: 0; z-index: 100; }}
  .logo {{ font-size: 18px; font-weight: 700; color: #1E293B; padding: 16px 0; white-space: nowrap; }}
  .logo span {{ color: #4F46E5; }}
  nav {{ display: flex; }}
  .nav-btn {{ padding: 20px 18px; border: none; background: none; font-size: 14px; font-weight: 500; color: #64748B; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.15s; white-space: nowrap; }}
  .nav-btn:hover {{ color: #4F46E5; }}
  .nav-btn.active {{ color: #4F46E5; border-bottom-color: #4F46E5; font-weight: 600; }}
  .header-right {{ margin-left: auto; display: flex; align-items: center; gap: 16px; }}
  .timestamp {{ font-size: 12px; color: #94A3B8; white-space: nowrap; }}
  .sync-btn {{ padding: 7px 16px; background: #4F46E5; color: white; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; white-space: nowrap; display: flex; align-items: center; gap: 6px; }}
  .sync-btn:hover {{ background: #4338CA; }}
  .sync-btn:disabled {{ background: #CBD5E1; cursor: not-allowed; }}
  .sync-btn.running {{ background: #D97706; animation: pulse 1s infinite; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.7; }} }}
  .sync-status {{ font-size: 11px; color: #94A3B8; white-space: nowrap; }}
  .page {{ display: none; }}
  .page.active {{ display: block; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 28px 32px; }}
  .section {{ background: white; border-radius: 12px; padding: 24px; border: 1px solid #E2E8F0; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .section h2 {{ font-size: 15px; font-weight: 600; color: #374151; margin-bottom: 16px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }}
  .stat-card {{ background: white; border-radius: 12px; padding: 20px; border: 1px solid #E2E8F0; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }}
  .stat-card .label {{ font-size: 12px; color: #94A3B8; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 500; }}
  .stat-card .value {{ font-size: 32px; font-weight: 700; color: #1E293B; }}
  .stat-card .sub {{ font-size: 12px; color: #94A3B8; margin-top: 4px; }}
  .bar-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }}
  .bar-label {{ width: 80px; font-size: 12px; color: #64748B; text-align: right; flex-shrink: 0; }}
  .bar-bg {{ flex: 1; background: #F1F5F9; border-radius: 4px; overflow: hidden; }}
  .bar-fill {{ background: linear-gradient(90deg, #4F46E5, #818CF8); height: 22px; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 11px; font-weight: 600; color: white; min-width: 28px; }}
  .stat-pill {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; color: white; margin: 3px; }}
  .filter-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
  .filter-btn {{ padding: 6px 14px; border-radius: 20px; border: 1px solid #E2E8F0; background: white; color: #64748B; cursor: pointer; font-size: 13px; transition: all 0.15s; }}
  .filter-btn:hover {{ border-color: var(--fc, #4F46E5); color: var(--fc, #4F46E5); }}
  .filter-btn.active {{ background: var(--fc, #4F46E5); border-color: var(--fc, #4F46E5); color: white; }}
  .sort-row {{ display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }}
  .sort-row label {{ font-size: 13px; color: #64748B; }}
  .search-box {{ margin-left: auto; width: 260px; max-width: 50%; border: 1px solid #E2E8F0; border-radius: 8px; padding: 7px 12px; font-size: 13px; color: #1E293B; outline: none; transition: all 0.15s; }}
  .search-box:focus {{ border-color: #4F46E5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); width: 320px; }}
  .search-count {{ font-size: 12px; color: #94A3B8; white-space: nowrap; }}
  select {{ background: white; border: 1px solid #E2E8F0; color: #374151; padding: 6px 12px; border-radius: 8px; font-size: 13px; cursor: pointer; }}
  .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
  .cards-area {{ min-height: 58vh; }}
  .no-results {{ text-align: center; color: #94A3B8; font-size: 14px; padding: 80px 20px; }}
  .collapsible {{ max-height: 84px; overflow: hidden; transition: max-height 0.25s ease; }}
  .collapsible.expanded {{ max-height: 2000px; }}
  .more-btn {{ margin-top: 8px; background: none; border: none; color: #4F46E5; font-size: 12px; font-weight: 600; cursor: pointer; padding: 2px 0; }}
  .more-btn:hover {{ text-decoration: underline; }}
  .market-card {{ background: #FAFAFA; border-radius: 12px; border: 1px solid #E2E8F0; overflow: hidden; transition: transform 0.15s, box-shadow 0.15s; position: relative; }}
  .market-card:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.08); }}
  .market-card.hidden {{ display: none; }}
  .market-card.locked {{ border-color: #F59E0B; box-shadow: 0 0 0 2px rgba(245,158,11,0.2); background: #FFFBEB; }}
  .card-header {{ padding: 12px 16px; display: flex; align-items: center; gap: 8px; background: white; border-bottom: 1px solid #F1F5F9; }}
  .type-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; color: white; }}
  .target-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; color: white; }}
  .score {{ color: #F59E0B; font-size: 13px; letter-spacing: 1px; }}
  .lock-btn {{ margin-left: auto; background: none; border: 1px solid #E2E8F0; border-radius: 6px; padding: 2px 8px; cursor: pointer; font-size: 14px; transition: all 0.15s; color: #94A3B8; white-space: nowrap; }}
  .lock-btn:hover {{ background: #FEF3C7; border-color: #F59E0B; }}
  .lock-btn.locked {{ background: #FEF3C7; border-color: #F59E0B; }}
  .reject-btn {{ background: none; border: 1px solid #E2E8F0; border-radius: 6px; padding: 2px 8px; cursor: pointer; font-size: 13px; transition: all 0.15s; color: #CBD5E1; white-space: nowrap; font-weight: 700; }}
  .reject-btn:hover {{ background: #FEF2F2; border-color: #FCA5A5; color: #EF4444; }}
  .market-card.rejected {{ opacity: 0.35; filter: grayscale(60%); }}
  .market-card.rejected .card-body {{ pointer-events: none; }}
  .rejected-overlay {{ display: none; position: absolute; inset: 0; background: rgba(239,68,68,0.06); border-radius: 12px; align-items: center; justify-content: center; flex-direction: column; gap: 4px; pointer-events: none; }}
  .market-card.rejected .rejected-overlay {{ display: flex; }}
  .rejected-label {{ font-size: 12px; font-weight: 700; color: #EF4444; background: white; padding: 3px 10px; border-radius: 20px; border: 1px solid #FCA5A5; }}
  .rejected-reason {{ font-size: 11px; color: #94A3B8; max-width: 85%; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  /* 거절 모달 */
  .modal-backdrop {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1000; align-items: center; justify-content: center; }}
  .modal-backdrop.open {{ display: flex; }}
  .modal {{ background: white; border-radius: 16px; padding: 28px; width: 460px; max-width: 90vw; box-shadow: 0 20px 60px rgba(0,0,0,0.15); }}
  .modal h3 {{ font-size: 16px; font-weight: 700; color: #1E293B; margin-bottom: 6px; }}
  .modal .modal-question {{ font-size: 13px; color: #64748B; background: #F8FAFC; padding: 10px 14px; border-radius: 8px; margin-bottom: 16px; line-height: 1.5; border-left: 3px solid #E2E8F0; }}
  .modal label {{ font-size: 13px; font-weight: 600; color: #374151; display: block; margin-bottom: 8px; }}
  .reject-reasons {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }}
  .reason-chip {{ padding: 5px 12px; border-radius: 20px; border: 1px solid #E2E8F0; background: white; font-size: 12px; color: #64748B; cursor: pointer; transition: all 0.15s; }}
  .reason-chip:hover, .reason-chip.selected {{ background: #FEE2E2; border-color: #FCA5A5; color: #DC2626; font-weight: 600; }}
  .modal textarea {{ width: 100%; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 12px; font-size: 13px; color: #374151; resize: vertical; min-height: 72px; font-family: inherit; outline: none; box-sizing: border-box; }}
  .modal textarea:focus {{ border-color: #EF4444; box-shadow: 0 0 0 3px rgba(239,68,68,0.1); }}
  .modal-footer {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }}
  .btn-cancel {{ padding: 8px 18px; border: 1px solid #E2E8F0; border-radius: 8px; background: white; color: #64748B; cursor: pointer; font-size: 13px; font-weight: 500; }}
  .btn-cancel:hover {{ background: #F8FAFC; }}
  .btn-reject {{ padding: 8px 18px; border: none; border-radius: 8px; background: #EF4444; color: white; cursor: pointer; font-size: 13px; font-weight: 600; }}
  .btn-reject:hover {{ background: #DC2626; }}
  /* 상세 검수 모달 */
  .modal-lg {{ width: 600px; max-width: 94vw; max-height: 90vh; overflow-y: auto; }}
  .modal-lg .field {{ margin-bottom: 16px; }}
  .modal-lg .field label {{ font-size: 12px; font-weight: 700; color: #475569; display: block; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.03em; }}
  .modal-lg input[type=text], .modal-lg textarea {{ width: 100%; border: 1px solid #E2E8F0; border-radius: 8px; padding: 9px 12px; font-size: 13px; color: #1E293B; font-family: inherit; outline: none; box-sizing: border-box; }}
  .modal-lg input[type=text]:focus, .modal-lg textarea:focus {{ border-color: #4F46E5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }}
  .modal-lg textarea {{ resize: vertical; min-height: 60px; line-height: 1.5; }}
  .detail-meta {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; align-items: center; }}
  .insight-box {{ background: #F5F3FF; border: 1px solid #DDD6FE; border-radius: 8px; }}
  .insight-box:focus {{ background: white; }}
  .field-hint {{ font-size: 11px; color: #94A3B8; margin-top: 4px; font-weight: 400; text-transform: none; letter-spacing: 0; }}
  .btn-publish {{ padding: 9px 22px; border: none; border-radius: 8px; background: #4F46E5; color: white; cursor: pointer; font-size: 14px; font-weight: 700; }}
  .btn-publish:hover {{ background: #4338CA; }}
  .btn-publish:disabled {{ background: #CBD5E1; cursor: not-allowed; }}
  /* 참여자 프로파일링 섹션 */
  .participant-section {{ margin-top: 18px; padding-top: 16px; border-top: 2px dashed #E2E8F0; }}
  .ps-title {{ font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }}
  .ps-status {{ font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 10px; }}
  .ps-status.draft {{ background: #FEF3C7; color: #B45309; }}
  .ps-status.live {{ background: #DCFCE7; color: #16A34A; }}
  .ps-recommend {{ margin-bottom: 12px; }}
  .ps-rec-label {{ font-size: 12px; font-weight: 700; color: #4338CA; margin-bottom: 8px; }}
  .ps-seg {{ display: flex; align-items: center; gap: 8px; padding: 7px 10px; background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 8px; margin-bottom: 6px; }}
  .ps-seg-rank {{ font-size: 10px; font-weight: 700; color: white; background: #4F46E5; padding: 2px 7px; border-radius: 10px; white-space: nowrap; flex-shrink: 0; }}
  .ps-seg-axis {{ font-size: 13px; font-weight: 700; color: #312E81; white-space: nowrap; flex-shrink: 0; }}
  .ps-seg-reason {{ font-size: 11px; color: #64748B; line-height: 1.4; }}
  .ps-rec-star {{ font-size: 10px; font-weight: 700; color: #4F46E5; background: #EEF2FF; padding: 1px 6px; border-radius: 8px; }}
  .ps-guide {{ font-size: 12px; color: #475569; background: #F5F3FF; border-left: 3px solid #C7D2FE; padding: 9px 12px; border-radius: 0 6px 6px 0; line-height: 1.55; }}
  .ps-stats {{ margin-top: 12px; }}
  .ps-mock-note {{ font-size: 11px; color: #94A3B8; margin-bottom: 10px; line-height: 1.5; }}
  .ps-block {{ margin-bottom: 12px; }}
  .ps-block-label {{ font-size: 11px; font-weight: 700; color: #64748B; margin-bottom: 6px; }}
  .ps-bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 5px; }}
  .ps-bar-name {{ width: 66px; font-size: 11px; color: #64748B; text-align: right; flex-shrink: 0; }}
  .ps-bar-track {{ flex: 1; background: #F1F5F9; border-radius: 4px; overflow: hidden; }}
  .ps-bar-fill {{ height: 18px; border-radius: 4px; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; font-size: 10px; font-weight: 700; color: white; min-width: 22px; transition: width 0.3s; }}
  .ps-insight {{ margin-top: 10px; font-size: 13px; color: #334155; line-height: 1.6; background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 12px; }}
  /* 수집 내역 - 수동 발행 / 자동 키워드 */
  .manual-row {{ display: flex; gap: 10px; align-items: center; }}
  .manual-row input {{ flex: 1; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px; font-size: 14px; outline: none; }}
  .manual-row input:focus {{ border-color: #4F46E5; box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }}
  .gen-btn {{ padding: 10px 18px; background: #4F46E5; color: white; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; }}
  .gen-btn:hover {{ background: #4338CA; }}
  .gen-btn:disabled {{ background: #CBD5E1; cursor: not-allowed; }}
  .kw-row {{ display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid #F1F5F9; }}
  .kw-row:last-child {{ border-bottom: none; }}
  .kw-domain {{ background: #EEF2FF; color: #4F46E5; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  .kw-name {{ flex: 1; font-size: 13px; color: #374151; }}
  .kw-gen-btn {{ padding: 4px 12px; background: white; color: #4F46E5; border: 1px solid #C7D2FE; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; }}
  .kw-gen-btn:hover {{ background: #4F46E5; color: white; }}
  .kw-gen-btn:disabled {{ background: #F1F5F9; color: #CBD5E1; border-color: #E2E8F0; cursor: not-allowed; }}
  .tag-chip {{ display: inline-block; background: #EEF2FF; color: #4F46E5; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
  /* 제외 이력 탭 */
  .reject-counts {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .reject-count-pill {{ display: inline-flex; align-items: center; gap: 6px; background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
  .reject-count-pill b {{ font-size: 13px; }}
  .analyze-result {{ margin-top: 16px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px; }}
  .analyze-result h4 {{ font-size: 13px; font-weight: 700; color: #334155; margin: 0 0 8px; }}
  .analyze-result .diag {{ font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 14px; }}
  .analyze-result ul {{ margin: 0 0 14px; padding-left: 18px; }}
  .analyze-result li {{ font-size: 13px; color: #475569; line-height: 1.6; margin-bottom: 4px; }}
  .improve-box {{ background: #1E293B; color: #E2E8F0; border-radius: 8px; padding: 14px; font-family: ui-monospace, monospace; font-size: 12px; line-height: 1.6; white-space: pre-wrap; position: relative; }}
  .copy-btn {{ position: absolute; top: 8px; right: 8px; background: #475569; color: white; border: none; border-radius: 6px; padding: 3px 10px; font-size: 11px; cursor: pointer; }}
  .copy-btn:hover {{ background: #64748B; }}
  .rj-row {{ padding: 11px 0; border-bottom: 1px solid #F1F5F9; }}
  .rj-row:last-child {{ border-bottom: none; }}
  .rj-q {{ font-size: 13px; font-weight: 600; color: #1E293B; margin-bottom: 5px; }}
  .rj-reasons {{ display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }}
  .rj-reason {{ background: #FEE2E2; color: #B91C1C; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
  .rj-memo {{ font-size: 11px; color: #94A3B8; font-style: italic; }}
  .rj-date {{ font-size: 11px; color: #CBD5E1; margin-left: auto; }}
  .card-body {{ padding: 14px 16px; cursor: pointer; }}
  .question {{ font-size: 14px; font-weight: 600; color: #1E293B; margin-bottom: 10px; line-height: 1.5; }}
  .options {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }}
  .option-chip {{ background: white; border: 1px solid #E2E8F0; padding: 3px 10px; border-radius: 6px; font-size: 12px; color: #374151; }}
  .source-row {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 8px; }}
  .source-title {{ font-size: 11px; color: #94A3B8; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .source-link {{ font-size: 11px; color: #4F46E5; text-decoration: none; white-space: nowrap; font-weight: 500; }}
  .source-link:hover {{ text-decoration: underline; }}
  .source-link-none {{ font-size: 11px; color: #CBD5E1; white-space: nowrap; }}
  .creative-badge {{ font-size: 11px; color: #7C3AED; white-space: nowrap; font-weight: 600; background: #F5F3FF; padding: 1px 6px; border-radius: 4px; }}
  .rationale {{ font-size: 11px; color: #94A3B8; font-style: italic; line-height: 1.4; }}
  .insight-blurb {{ font-size: 12px; color: #475569; line-height: 1.5; background: #F8FAFC; border-left: 3px solid #C7D2FE; padding: 7px 10px; border-radius: 0 6px 6px 0; }}
  .locked-ribbon {{ position: absolute; top: 8px; right: 8px; background: #F59E0B; color: white; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; display: none; }}
  .market-card.locked .locked-ribbon {{ display: block; }}
  .issue-row {{ display: flex; align-items: flex-start; gap: 8px; padding: 8px 0; border-bottom: 1px solid #F8FAFC; }}
  .issue-row:last-child {{ border-bottom: none; }}
  .cat-badge {{ background: #EEF2FF; color: #4F46E5; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 600; white-space: nowrap; flex-shrink: 0; margin-top: 1px; }}
  .issue-title-text {{ font-size: 13px; color: #374151; flex: 1; line-height: 1.4; }}
  .market-row {{ padding: 10px 12px; border-radius: 8px; border: 1px solid #E2E8F0; margin-bottom: 8px; background: white; transition: background 0.2s, border-color 0.2s; }}
  .market-row.applied {{ background: #F0FDF4; border-color: #BBF7D0; }}
  .market-row:last-child {{ margin-bottom: 0; }}
  .history-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .empty-state {{ color: #94A3B8; text-align: center; padding: 60px; }}
  .toast {{ position: fixed; bottom: 24px; right: 24px; background: #1E293B; color: white; padding: 12px 20px; border-radius: 10px; font-size: 13px; font-weight: 500; z-index: 9999; transform: translateY(80px); opacity: 0; transition: all 0.3s; pointer-events: none; }}
  .toast.show {{ transform: translateY(0); opacity: 1; }}
</style>
</head>
<body>

<header>
  <div class="logo">폴리볼 <span>이슈</span> 수집</div>
  <nav>
    <button class="nav-btn active" onclick="showPage('dashboard', this)">📊 대시보드</button>
    <button class="nav-btn" onclick="showPage('history', this)">📋 수집 내역</button>
    <button class="nav-btn" onclick="showPage('rejects', this)">🚫 제외 이력</button>
  </nav>
  <div class="header-right">
    <span class="sync-status" id="syncStatus"></span>
    <button class="sync-btn" id="syncBtn" onclick="doSync()" title="새 이슈를 수집하고 마켓 초안을 갱신합니다 (잠금 카드 유지)">🔄 동기화</button>
    <span class="timestamp">마지막 수집: {now}</span>
  </div>
</header>

<div id="page-dashboard" class="page active">
  <div class="container">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="label">수집된 이슈</div>
        <div class="value">{len(issues)}</div>
        <div class="sub">중복 제거 후</div>
      </div>
      <div class="stat-card">
        <div class="label">생성된 마켓 초안</div>
        <div class="value">{len(markets)}</div>
        <div class="sub">검수 대기 중</div>
      </div>
      <div class="stat-card">
        <div class="label">평균 마켓화 점수</div>
        <div class="value">{avg_score:.1f}</div>
        <div class="sub">/ 5점 만점</div>
      </div>
      <div class="stat-card">
        <div class="label">수집 카테고리</div>
        <div class="value">{len(category_counts)}</div>
        <div class="sub">{", ".join(list(category_counts.keys())[:3])} 등</div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
      <div class="section">
        <h2>카테고리별 이슈 수</h2>
        {category_bars}
      </div>
      <div class="section">
        <h2>마켓 유형 분포</h2>
        <div style="margin-bottom:16px">{type_pills}</div>
        <h2 style="margin-top:16px">타겟 분포</h2>
        <div class="collapsible" id="targetPills">{target_pills}</div>
        <button class="more-btn" id="targetMoreBtn" onclick="toggleTargets()" style="display:none">더보기 ▾</button>
      </div>
    </div>

    <div class="section">
      <h2>마켓 초안 목록 <span id="lockCountBadge" style="font-size:12px;color:#F59E0B;font-weight:600;margin-left:8px"></span></h2>
      <div class="sort-row">
        <label>정렬:</label>
        <select onchange="sortCards(this.value)">
          <option value="score">마켓화 점수 높은 순</option>
          <option value="type">마켓 유형별</option>
        </select>
        <input type="text" class="search-box" id="cardSearch" placeholder="🔍 키워드·질문 검색..." oninput="searchCards(this.value)">
        <span class="search-count" id="searchCount"></span>
      </div>
      <div class="filter-row">{filter_buttons}</div>
      <div class="cards-area">
        <div class="cards-grid" id="cardsGrid">{market_cards}</div>
        <div class="no-results" id="noResults" style="display:none">🔍 조회 결과가 없습니다.</div>
      </div>
    </div>
  </div>
</div>

<div id="page-history" class="page">
  <div class="container">
    <div class="section">
      <h2>✍️ 관리자 수동 발행</h2>
      <p style="font-size:12px;color:#94A3B8;margin:-8px 0 14px">키워드를 입력하면 AI가 <b>구글 실시간 검색</b>으로 조사한 뒤 마켓 초안을 만들어 대시보드로 보냅니다. (~30초)</p>
      <div class="manual-row">
        <input type="text" id="manualKeyword" placeholder="예: SK하이닉스 주가, 손흥민 월드컵, 참교육 시즌2..." onkeydown="if(event.key==='Enter')generateFromKeyword(this.value, null)">
        <button class="gen-btn" id="manualGenBtn" onclick="generateFromKeyword(document.getElementById('manualKeyword').value, null)">🤖 AI 마켓 생성요청</button>
      </div>
    </div>

    <div class="section">
      <h2>📡 실시간 자동 키워드 <span style="font-size:12px;color:#94A3B8;font-weight:400" id="autoKwCount"></span></h2>
      <p style="font-size:12px;color:#94A3B8;margin:-8px 0 14px">하이브리드 엔진이 자동 추출한 트렌드 키워드입니다. [즉시 마켓 생성]으로 바로 초안화할 수 있습니다.</p>
      <div id="autoKeywordList"><p class="empty-state">키워드 없음</p></div>
    </div>

    <div class="section" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <h2 style="margin:0">📋 수집 내역</h2>
        <select id="historyDateSelect" onchange="loadHistoryDate(this.value)">
          {history_date_options}
        </select>
        <span id="historyStats" style="font-size:13px;color:#64748B"></span>
      </div>
    </div>
    <div class="history-grid">
      <div class="section" style="max-height:72vh;overflow-y:auto">
        <h2 style="margin-bottom:12px">이슈 목록 <span id="issueCount" style="font-size:13px;color:#94A3B8;font-weight:400"></span></h2>
        <div id="issueList"><p class="empty-state">날짜를 선택하세요</p></div>
      </div>
      <div class="section" style="max-height:72vh;overflow-y:auto">
        <h2 style="margin-bottom:12px">마켓 초안 <span id="marketCount" style="font-size:13px;color:#94A3B8;font-weight:400"></span></h2>
        <div id="marketList"><p class="empty-state">날짜를 선택하세요</p></div>
      </div>
    </div>
  </div>
</div>

<div id="page-rejects" class="page">
  <div class="container">
    <div class="section">
      <h2>🚫 제외(거절) 사유 분석 <span id="rejectTotal" style="font-size:12px;color:#EF4444;font-weight:600;margin-left:6px"></span></h2>
      <p style="font-size:12px;color:#94A3B8;margin:-8px 0 14px">제외된 마켓과 사유를 누적 기록만 합니다. <b>자동 분석은 하지 않으며</b>, 아래 버튼을 눌렀을 때만 AI가 1회 분석해 프롬프트 개선안을 제시합니다.</p>
      <div id="rejectCounts" class="reject-counts"></div>
      <div style="margin-top:14px">
        <button class="gen-btn" id="analyzeBtn" onclick="analyzeRejects()" style="background:#EF4444">🤖 거절 패턴 분석 &amp; 프롬프트 개선안 도출</button>
        <span style="font-size:11px;color:#94A3B8;margin-left:10px">클릭 시에만 AI 호출 (~20초)</span>
      </div>
      <div id="analyzeResult" class="analyze-result" style="display:none"></div>
    </div>
    <div class="section">
      <h2>제외 마켓 목록 <span id="rejectListCount" style="font-size:13px;color:#94A3B8;font-weight:400"></span></h2>
      <div id="rejectList"><p class="empty-state">제외된 마켓이 없습니다</p></div>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<!-- 거절 모달 -->
<div class="modal-backdrop" id="rejectBackdrop" onclick="closeRejectModal(event)">
  <div class="modal">
    <h3>🚫 마켓 제외</h3>
    <div class="modal-question" id="rejectQuestion"></div>
    <label>제외 사유 선택 (복수 선택 가능)</label>
    <div class="reject-reasons">
      <span class="reason-chip" onclick="toggleReasonChip(this)">이미 지난 이슈</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">결과가 이미 알려진 내용</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">마켓 매력도 낮음</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">타겟과 맞지 않음</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">선택지가 부적절</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">정보가 부정확함</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">민감한 주제</span>
      <span class="reason-chip" onclick="toggleReasonChip(this)">유사 마켓 이미 존재</span>
    </div>
    <label>추가 메모 (선택)</label>
    <textarea id="rejectMemo" placeholder="구체적인 사유나 개선 방향을 입력하세요..."></textarea>
    <div class="modal-footer">
      <button class="btn-cancel" onclick="closeRejectModal(null)">취소</button>
      <button class="btn-reject" onclick="confirmReject()">제외하기</button>
    </div>
  </div>
</div>

<!-- 상세 검수 모달 -->
<div class="modal-backdrop" id="detailBackdrop" onclick="closeDetailModal(event)">
  <div class="modal modal-lg" onclick="event.stopPropagation()">
    <h3>📝 마켓 상세 검수</h3>
    <div class="detail-meta" id="detailMeta"></div>

    <div class="field">
      <label>질문 (poll_question)</label>
      <textarea id="d_question" rows="2"></textarea>
    </div>
    <div class="field">
      <label>선택지 (options) <span class="field-hint">한 줄에 하나씩</span></label>
      <textarea id="d_options" rows="4"></textarea>
    </div>
    <div class="field">
      <label>트렌드 태그 (trend_tags) <span class="field-hint">쉼표로 구분 · 예: #서학개미, #퇴사각</span></label>
      <input type="text" id="d_tags" placeholder="#태그1, #태그2, #태그3">
    </div>
    <div class="field">
      <label>AI 트렌드 시사점 (content_insight)</label>
      <textarea id="d_insight" class="insight-box" rows="3"></textarea>
    </div>
    <div class="field">
      <label>정산 기준 (resolution_criteria)</label>
      <textarea id="d_resolution" rows="2"></textarea>
    </div>
    <div class="field">
      <label>푸시 카피 (push_notification_headline)</label>
      <input type="text" id="d_push">
    </div>

    <div class="participant-section">
      <div class="ps-title">👥 참여자 프로파일링 리포트 <span id="psStatus" class="ps-status"></span></div>
      <div id="psRecommend" class="ps-recommend"></div>
      <div id="psGuide" class="ps-guide"></div>
      <div id="psStats" class="ps-stats"></div>
      <div id="psInsightWrap" style="display:none">
        <button class="gen-btn" id="psInsightBtn" onclick="genParticipantInsight()" style="margin-top:12px">🤖 AI 참여자 분석 리포트 생성</button>
        <span style="font-size:11px;color:#94A3B8;margin-left:8px">클릭 시에만 AI 호출 (~15초)</span>
        <div id="psInsight" class="ps-insight" style="display:none"></div>
      </div>
    </div>

    <div class="modal-footer">
      <button class="btn-cancel" onclick="closeDetailModal(null)">닫기</button>
      <button class="btn-publish" id="publishBtn" onclick="publishMarket()">🚀 최종 발행/배포</button>
    </div>
  </div>
</div>

<script>
// ── 데이터 ──────────────────────────────────────────
const HISTORY_DATA = {history_data_js};
const MARKETS_DATA = {markets_data_js};
const AUTO_KEYWORDS = {auto_keywords_js};
const REJECTS_DATA = {rejects_data_js};
const PUBLISHED_QUESTIONS = {published_q_js};
const TYPE_COLORS = {type_color_js};
const TYPE_KO = {type_ko_js};
const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

// ── 토스트 ──────────────────────────────────────────
function showToast(msg, duration) {{
  if (duration === undefined) duration = 2500;
  var t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(function() {{ t.classList.remove('show'); }}, duration);
}}

// ── 페이지 전환 ──────────────────────────────────────
function showPage(name, btn) {{
  document.querySelectorAll('.page').forEach(function(p) {{ p.classList.remove('active'); }});
  document.querySelectorAll('.nav-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  document.getElementById('page-' + name).classList.add('active');
  btn.classList.add('active');
  if (name === 'history') {{
    var sel = document.getElementById('historyDateSelect');
    if (sel && sel.value) loadHistoryDate(sel.value);
  }}
  if (name === 'rejects') {{
    loadRejects();
  }}
}}

// ── 필터 / 정렬 ──────────────────────────────────────
// 보이는 카드가 0이면 '조회 결과 없음' 표시 (영역 높이는 .cards-area가 고정)
function updateNoResults() {{
  var visible = 0;
  document.querySelectorAll('.market-card').forEach(function(c) {{ if (!c.classList.contains('hidden')) visible++; }});
  var nr = document.getElementById('noResults');
  if (nr) nr.style.display = visible === 0 ? 'block' : 'none';
}}

// 타겟 분포 더보기/접기
function toggleTargets() {{
  var el = document.getElementById('targetPills');
  var btn = document.getElementById('targetMoreBtn');
  if (!el) return;
  var expanded = el.classList.toggle('expanded');
  if (btn) btn.textContent = expanded ? '접기 ▴' : '더보기 ▾';
}}

function filterCards(type, btn) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  var sb = document.getElementById('cardSearch'); if (sb) sb.value = '';
  document.querySelectorAll('.market-card').forEach(function(card) {{
    card.classList.toggle('hidden', type !== 'all' && card.dataset.type !== type);
  }});
  updateNoResults();
}}
function filterCreative(btn) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.market-card').forEach(function(card) {{
    card.classList.toggle('hidden', card.dataset.sourcetype !== 'creative');
  }});
  updateNoResults();
}}
function filterLocked(btn) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.market-card').forEach(function(card) {{
    card.classList.toggle('hidden', !card.classList.contains('locked'));
  }});
  updateNoResults();
}}
function sortCards(by) {{
  var grid = document.getElementById('cardsGrid');
  var cards = Array.from(grid.children);
  cards.sort(function(a, b) {{
    if (by === 'score') return parseInt(b.dataset.score) - parseInt(a.dataset.score);
    if (by === 'type') return a.dataset.type.localeCompare(b.dataset.type);
    return 0;
  }});
  cards.forEach(function(c) {{ grid.appendChild(c); }});
}}

function searchCards(q) {{
  q = (q || '').trim().toLowerCase();
  // 검색 중에는 유형/잠금 필터 버튼 활성 해제 (독립 동작)
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  var shown = 0, total = 0;
  document.querySelectorAll('.market-card').forEach(function(card) {{
    total++;
    var txt = card.dataset.search || '';
    var hit = q === '' || txt.indexOf(q) !== -1;
    card.classList.toggle('hidden', !hit);
    if (hit) shown++;
  }});
  var cnt = document.getElementById('searchCount');
  if (cnt) cnt.textContent = q === '' ? '' : (shown + ' / ' + total + '개');
  // 검색어 비우면 '전체' 필터 활성 복원
  if (q === '') {{
    var first = document.querySelector('.filter-btn');
    if (first) first.classList.add('active');
  }}
  updateNoResults();
}}

// ── 잠금 시스템 ──────────────────────────────────────
var LOCK_KEY = 'polyball_locked_idxs';

function getLockedIdxs() {{
  try {{ return new Set(JSON.parse(localStorage.getItem(LOCK_KEY) || '[]')); }}
  catch(e) {{ return new Set(); }}
}}
function saveLockedIdxs(s) {{
  try {{ localStorage.setItem(LOCK_KEY, JSON.stringify(Array.from(s))); }}
  catch(e) {{}}
}}

function toggleLock(idx, btn) {{
  var card = document.getElementById('mcard-' + idx);
  if (!card) return;
  var locked = getLockedIdxs();
  if (locked.has(idx)) {{
    locked.delete(idx);
    card.classList.remove('locked');
    btn.classList.remove('locked');
    btn.textContent = '🔓';
    btn.title = '잠금 시 동기화해도 유지됨';
    showToast('잠금 해제됨');
  }} else {{
    locked.add(idx);
    card.classList.add('locked');
    btn.classList.add('locked');
    btn.textContent = '🔒';
    btn.title = '잠금됨 – 동기화 시 유지';
    showToast('🔒 잠금됨 – 동기화해도 유지됩니다');
  }}
  saveLockedIdxs(locked);
  updateLockBadge();
  if (IS_LOCAL) syncLocksToServer();
}}

function updateLockBadge() {{
  var cnt = getLockedIdxs().size;
  var badge = document.getElementById('lockCountBadge');
  if (badge) badge.textContent = cnt > 0 ? '🔒 ' + cnt + '개 잠금' : '';
}}

function restoreLockUI() {{
  var locked = getLockedIdxs();
  locked.forEach(function(idx) {{
    var card = document.getElementById('mcard-' + idx);
    if (!card) return;
    card.classList.add('locked');
    var btn = card.querySelector('.lock-btn');
    if (btn) {{ btn.classList.add('locked'); btn.textContent = '🔒'; btn.title = '잠금됨 – 동기화 시 유지'; }}
  }});
  updateLockBadge();
}}

function syncLocksToServer() {{
  if (!IS_LOCAL) return;
  var locked = getLockedIdxs();
  var lockedMarkets = Array.from(locked).map(function(i) {{ return MARKETS_DATA[i]; }}).filter(Boolean);
  fetch('/api/locks', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(lockedMarkets)
  }}).catch(function(e) {{}});
}}

// 서버에서 잠금 목록 로드 (로컬 서버 모드)
function loadLocksFromServer() {{
  if (!IS_LOCAL) return;
  fetch('/api/locks').then(function(r) {{ return r.json(); }}).then(function(lockedMarkets) {{
    if (!lockedMarkets || !lockedMarkets.length) return;
    var lockedQs = new Set(lockedMarkets.map(function(m) {{ return m.question; }}));
    var newSet = new Set();
    MARKETS_DATA.forEach(function(m, idx) {{
      if (lockedQs.has(m.question)) newSet.add(idx);
    }});
    saveLockedIdxs(newSet);
    restoreLockUI();
  }}).catch(function(e) {{}});
}}

// ── 동기화 버튼 ──────────────────────────────────────
var syncPollInterval = null;

function doSync() {{
  if (!IS_LOCAL) {{
    showToast('⚠️ 동기화는 로컬 서버(python server.py)에서만 가능합니다', 3500);
    return;
  }}
  var btn = document.getElementById('syncBtn');
  btn.disabled = true;
  btn.classList.add('running');
  btn.textContent = '⏳ 동기화 중...';
  document.getElementById('syncStatus').textContent = '수집·생성 중... (~4-5분 소요)';
  showToast('🔄 동기화 시작! 약 4-5분 후 자동으로 새로고침됩니다', 4000);

  fetch('/api/sync', {{ method: 'POST' }})
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      if (!data.ok) {{
        showToast('⚠️ ' + (data.message || '동기화 실패'), 3000);
        resetSyncBtn();
        return;
      }}
      syncPollInterval = setInterval(function() {{
        fetch('/api/sync/status')
          .then(function(r) {{ return r.json(); }})
          .then(function(s) {{
            if (!s.running) {{
              clearInterval(syncPollInterval);
              document.getElementById('syncStatus').textContent = '완료 ' + s.last;
              showToast('✅ 동기화 완료! 새로고침합니다...', 2000);
              setTimeout(function() {{ window.location.reload(); }}, 2200);
            }}
          }}).catch(function(e) {{}});
      }}, 5000);
    }})
    .catch(function(e) {{
      showToast('⚠️ 서버 연결 실패. python server.py가 실행 중인지 확인하세요.', 4000);
      resetSyncBtn();
    }});
}}

function resetSyncBtn() {{
  var btn = document.getElementById('syncBtn');
  if (!btn) return;
  btn.disabled = false;
  btn.classList.remove('running');
  btn.textContent = '🔄 동기화';
}}

// Vercel에서 동기화 버튼 비활성화 표시
function initSyncBtn() {{
  if (!IS_LOCAL) {{
    var btn = document.getElementById('syncBtn');
    if (!btn) return;
    btn.style.background = '#CBD5E1';
    btn.style.cursor = 'not-allowed';
    btn.title = 'Vercel 배포본에서는 로컬에서 run.py를 실행 후 GitHub에 푸시하세요';
    var statusEl = document.getElementById('syncStatus');
    if (statusEl) statusEl.textContent = '(로컬 전용 기능)';
  }}
}}

// ── 히스토리 탭 ──────────────────────────────────────
function loadHistoryDate(date) {{
  var data = HISTORY_DATA[date];
  if (!data) {{
    document.getElementById('issueList').innerHTML = '<p class="empty-state">데이터 없음</p>';
    document.getElementById('marketList').innerHTML = '<p class="empty-state">데이터 없음</p>';
    return;
  }}

  document.getElementById('issueCount').textContent = '(' + data.issues.length + '개)';
  document.getElementById('marketCount').textContent = '(' + data.markets.length + '개)';
  document.getElementById('historyStats').textContent =
    '이슈 ' + data.issues.length + '개 · 마켓 ' + data.markets.length + '개';

  // 이슈 목록
  if (data.issues.length === 0) {{
    document.getElementById('issueList').innerHTML = '<p class="empty-state">이슈 없음</p>';
  }} else {{
    document.getElementById('issueList').innerHTML = data.issues.map(function(issue) {{
      var linkHtml = issue.link
        ? '<a href="' + issue.link + '" target="_blank" style="color:#4F46E5;font-size:11px;white-space:nowrap;margin-left:6px;text-decoration:none;font-weight:500">원문↗</a>'
        : '';
      return '<div class="issue-row">' +
        '<span class="cat-badge">' + (issue.category || '') + '</span>' +
        '<span class="issue-title-text">' + issue.title + '</span>' +
        linkHtml + '</div>';
    }}).join('');
  }}

  // 마켓 목록
  if (data.markets.length === 0) {{
    document.getElementById('marketList').innerHTML = '<p class="empty-state">마켓 없음</p>';
  }} else {{
    document.getElementById('marketList').innerHTML = data.markets.map(function(m, i) {{
      var key = 'applied_' + date + '_' + i;
      var isApplied = localStorage.getItem(key) === 'true';
      var color = TYPE_COLORS[m.market_type] || '#6B7280';
      var typeLabel = TYPE_KO[m.market_type] || m.market_type;
      var linkHtml = m.source_link
        ? '<a href="' + m.source_link + '" target="_blank" style="color:#4F46E5;font-size:11px;text-decoration:none;font-weight:500">원문↗</a>'
        : (m.source_type === 'creative' ? '<span style="color:#7C3AED;font-size:10px;font-weight:600;background:#F5F3FF;padding:1px 5px;border-radius:3px">✨ AI</span>' : '');
      var appliedBadge = isApplied
        ? '<span style="background:#DCFCE7;color:#16A34A;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700">✓ 적용완료</span>'
        : '';
      return '<div class="market-row' + (isApplied ? ' applied' : '') + '" id="mrow-' + date + '-' + i + '">' +
        '<div style="display:flex;align-items:flex-start;gap:8px">' +
        '<input type="checkbox"' + (isApplied ? ' checked' : '') +
          ' onchange="toggleApplied(this.dataset.date, this.dataset.idx, this.checked)"' +
          ' data-date="' + date + '" data-idx="' + i + '"' +
          ' style="margin-top:4px;cursor:pointer;accent-color:#4F46E5;flex-shrink:0">' +
        '<div style="flex:1;min-width:0">' +
        '<div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;flex-wrap:wrap">' +
        '<span style="background:' + color + ';color:white;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700">' + typeLabel + '</span>' +
        appliedBadge + ' ' + linkHtml +
        '</div>' +
        '<p style="margin:0;font-size:13px;font-weight:600;color:#1E293B;line-height:1.4">' + m.question + '</p>' +
        '</div></div></div>';
    }}).join('');
  }}
}}

function toggleApplied(date, idx, checked) {{
  localStorage.setItem('applied_' + date + '_' + idx, checked ? 'true' : 'false');
  loadHistoryDate(date);
}}

// ── 거절(제외) 시스템 ────────────────────────────────
// 질문(question) 기반 — 마켓 순서/인덱스가 바뀌어도 안전 (잠금과 동일 전략)
var REJECT_KEY = 'polyball_rejected_q';
var _rejectTargetIdx = null;

function markCardRejected(idx, reasons) {{
  var card = document.getElementById('mcard-' + idx);
  if (!card) return;
  card.classList.add('rejected');
  card.classList.remove('locked');
  var lockBtn = card.querySelector('.lock-btn');
  if (lockBtn) {{ lockBtn.classList.remove('locked'); lockBtn.textContent = '🔓'; }}
  if (!card.querySelector('.rejected-overlay')) {{
    var overlay = document.createElement('div');
    overlay.className = 'rejected-overlay';
    overlay.innerHTML = '<span class="rejected-label">제외됨</span><span class="rejected-reason"></span>';
    card.appendChild(overlay);
  }}
  var rej = card.querySelector('.rejected-reason');
  if (rej) rej.textContent = (reasons || []).join(' · ');
}}

function getRejectedMap() {{
  try {{ return JSON.parse(localStorage.getItem(REJECT_KEY) || '{{}}'); }}
  catch(e) {{ return {{}}; }}
}}
function saveRejectedMap(map) {{
  try {{ localStorage.setItem(REJECT_KEY, JSON.stringify(map)); }}
  catch(e) {{}}
}}

function openRejectModal(idx) {{
  _rejectTargetIdx = idx;
  var market = MARKETS_DATA[idx];
  if (!market) return;
  document.getElementById('rejectQuestion').textContent = market.question || '';
  document.getElementById('rejectMemo').value = '';
  document.querySelectorAll('.reason-chip').forEach(function(c) {{ c.classList.remove('selected'); }});
  document.getElementById('rejectBackdrop').classList.add('open');
  setTimeout(function() {{ document.getElementById('rejectMemo').focus(); }}, 100);
}}

function closeRejectModal(e) {{
  if (e && e.target !== document.getElementById('rejectBackdrop')) return;
  document.getElementById('rejectBackdrop').classList.remove('open');
  _rejectTargetIdx = null;
}}

function toggleReasonChip(el) {{
  el.classList.toggle('selected');
}}

function confirmReject() {{
  var idx = _rejectTargetIdx;
  if (idx === null || idx === undefined) return;

  var chips = document.querySelectorAll('.reason-chip.selected');
  var reasons = Array.from(chips).map(function(c) {{ return c.textContent; }});
  var memo = document.getElementById('rejectMemo').value.trim();
  if (memo) reasons.push(memo);
  if (reasons.length === 0) {{
    reasons.push('사유 미입력');
  }}

  // 카드 UI 업데이트
  var card = document.getElementById('mcard-' + idx);
  if (card) {{
    card.classList.add('rejected');
    // 잠금 해제
    card.classList.remove('locked');
    var lockBtn = card.querySelector('.lock-btn');
    if (lockBtn) {{ lockBtn.classList.remove('locked'); lockBtn.textContent = '🔓'; }}
    // 거절 오버레이 추가 (없으면)
    if (!card.querySelector('.rejected-overlay')) {{
      var overlay = document.createElement('div');
      overlay.className = 'rejected-overlay';
      overlay.innerHTML = '<span class="rejected-label">제외됨</span><span class="rejected-reason">' + reasons[0] + '</span>';
      card.appendChild(overlay);
    }}
    var rej = card.querySelector('.rejected-reason');
    if (rej) rej.textContent = reasons.join(' · ');
  }}

  // localStorage 저장 (질문 기반 키)
  var map = getRejectedMap();
  var market = MARKETS_DATA[idx] || {{}};
  var now = new Date();
  var ts = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0') + '-' + String(now.getDate()).padStart(2,'0') + ' ' + String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
  if (market.question) {{
    map[market.question] = {{ reasons: reasons, memo: memo, rejected_at: ts }};
    saveRejectedMap(map);
  }}

  // 서버 저장 (로컬 모드)
  if (IS_LOCAL) {{
    var payload = Object.assign({{}}, market, {{
      rejected_reasons: reasons,
      rejected_memo: memo,
      rejected_at: ts
    }});
    fetch('/api/rejects', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload)
    }}).catch(function(e) {{}});
  }}

  closeRejectModal(null);
  showToast('제외 처리됐습니다');
}}

// 비로컬(Vercel): localStorage(질문 기반)로 복원
function restoreRejectedUI() {{
  var map = getRejectedMap();
  MARKETS_DATA.forEach(function(m, idx) {{
    if (!m || !map[m.question]) return;
    markCardRejected(idx, map[m.question].reasons || []);
  }});
}}

// 로컬 서버: 서버(/api/rejects)를 단일 출처로 복원 (인덱스 변동에 안전)
function loadRejectsFromServer() {{
  if (!IS_LOCAL) return;
  fetch('/api/rejects').then(function(r) {{ return r.json(); }}).then(function(list) {{
    if (!list) return;
    var byQ = {{}};
    list.forEach(function(r) {{ if (r.question) byQ[r.question] = r.rejected_reasons || []; }});
    var map = {{}};
    MARKETS_DATA.forEach(function(m, idx) {{
      if (m && byQ[m.question]) {{
        markCardRejected(idx, byQ[m.question]);
        map[m.question] = {{ reasons: byQ[m.question] }};
      }}
    }});
    saveRejectedMap(map);  // 로컬 캐시를 서버 기준으로 정리 (옛 인덱스 잔재 제거)
  }}).catch(function(e) {{ restoreRejectedUI(); }});
}}

// ── 상세 검수 모달 ───────────────────────────────────
var _detailIdx = null;

function openDetailModal(idx) {{
  _detailIdx = idx;
  var m = MARKETS_DATA[idx];
  if (!m) return;
  var color = TYPE_COLORS[m.market_type] || '#6B7280';
  var typeLabel = TYPE_KO[m.market_type] || m.market_type;
  var meta = '<span class="type-badge" style="background:' + color + '">' + typeLabel + '</span>';
  meta += '<span class="target-badge" style="background:#6B7280">' + (m.target_audience || '') + '</span>';
  var sc = m.scores || {{}};
  if (sc.timeliness) meta += '<span style="font-size:11px;color:#94A3B8">시의성 ' + sc.timeliness + ' · 정산 ' + sc.resolvability + ' · 공유 ' + sc.shareability + '</span>';
  if (m.source_link) meta += '<a href="' + m.source_link + '" target="_blank" class="source-link">📎 원문</a>';
  else if (m.source_type === 'creative') meta += '<span class="creative-badge">✨ AI 자유 제안</span>';
  document.getElementById('detailMeta').innerHTML = meta;
  document.getElementById('d_question').value = m.question || '';
  document.getElementById('d_options').value = (m.options || []).join('\\n');
  document.getElementById('d_tags').value = (m.trend_tags || []).join(', ');
  document.getElementById('d_insight').value = m.content_insight || '';
  document.getElementById('d_resolution').value = m.resolution_criteria || '';
  document.getElementById('d_push').value = m.push_notification_headline || '';
  renderParticipantSection(m);
  document.getElementById('detailBackdrop').classList.add('open');
}}

// ── 참여자 프로파일링 섹션 ───────────────────────────
var _recommendedAxes = [];

function renderParticipantSection(m) {{
  var published = PUBLISHED_QUESTIONS.indexOf(m.question) !== -1;
  var statusEl = document.getElementById('psStatus');
  var recEl = document.getElementById('psRecommend');
  var guideEl = document.getElementById('psGuide');
  var statsEl = document.getElementById('psStats');
  var insightWrap = document.getElementById('psInsightWrap');
  var insightEl = document.getElementById('psInsight');
  insightEl.style.display = 'none'; insightEl.innerHTML = '';

  // 📊 추천 분석 축 (핵심) — "어떤 지표로 묶어서 볼지" 우선순위
  var segs = m.recommended_segments || [];
  _recommendedAxes = segs.map(function(s) {{ return s.axis || ''; }});
  if (segs.length) {{
    var chips = segs.map(function(s, i) {{
      return '<div class="ps-seg"><span class="ps-seg-rank">' + (i + 1) + '순위</span>' +
        '<span class="ps-seg-axis">' + (s.axis || '') + '</span>' +
        '<span class="ps-seg-reason">' + (s.reason || '') + '</span></div>';
    }}).join('');
    recEl.innerHTML = '<div class="ps-rec-label">📊 추천 분석 축 — 이 지표로 묶어서 보세요</div>' + chips;
    recEl.style.display = 'block';
  }} else {{
    recEl.innerHTML = '<div class="ps-rec-label" style="color:#94A3B8">📊 추천 분석 축이 아직 없습니다 (동기화/재생성 시 채워집니다)</div>';
    recEl.style.display = 'block';
  }}

  var guide = m.audience_insight_guide || '';
  guideEl.innerHTML = guide
    ? ('🎯 <b>관전 포인트</b> ' + guide)
    : '';
  guideEl.style.display = guide ? 'block' : 'none';

  if (published) {{
    statusEl.textContent = '진행중'; statusEl.className = 'ps-status live';
    insightWrap.style.display = 'block';
    loadParticipantStats(m.question);
  }} else {{
    statusEl.textContent = '초안'; statusEl.className = 'ps-status draft';
    insightWrap.style.display = 'none';
    statsEl.innerHTML = '<div class="ps-mock-note">📭 아직 <b>초안</b> 상태입니다. 발행(🚀)하면 실제 참여자 통계(성별·연령·지역)와 AI 분석 리포트가 여기 표시됩니다.</div>';
  }}
}}

function loadParticipantStats(question) {{
  var statsEl = document.getElementById('psStats');
  if (!IS_LOCAL) {{ statsEl.innerHTML = '<div class="ps-mock-note">참여자 통계는 로컬 서버(python server.py)에서 확인 가능합니다.</div>'; return; }}
  statsEl.innerHTML = '<div class="ps-mock-note">불러오는 중...</div>';
  fetch('/api/participants?q=' + encodeURIComponent(question))
    .then(function(r) {{ return r.json(); }})
    .then(function(s) {{ renderParticipantBars(s); }})
    .catch(function(e) {{ statsEl.innerHTML = '<div class="ps-mock-note">통계 로드 실패</div>'; }});
}}

function renderParticipantBars(s) {{
  function isRecommended(label) {{
    return _recommendedAxes.some(function(a) {{ return a && a.indexOf(label) !== -1; }});
  }}
  function block(label, obj, colors) {{
    var keys = Object.keys(obj || {{}});
    var rows = keys.map(function(k, i) {{
      var v = obj[k];
      var c = colors[i % colors.length];
      return '<div class="ps-bar-row"><span class="ps-bar-name">' + k + '</span>' +
        '<div class="ps-bar-track"><div class="ps-bar-fill" style="width:' + Math.max(v, 3) + '%;background:' + c + '">' + v + '%</div></div></div>';
    }}).join('');
    var star = isRecommended(label) ? ' <span class="ps-rec-star">⭐ 추천 축</span>' : '';
    return '<div class="ps-block"><div class="ps-block-label">' + label + star + '</div>' + rows + '</div>';
  }}
  var html = '<div class="ps-mock-note">⚠️ <b>데모용 목업 데이터</b>입니다 (실제 유저 DB 연결 시 자동 교체) · 총 참여 ' + (s.total || 0) + '명</div>';
  html += block('성별', s.gender, ['#3B82F6', '#EC4899']);
  html += block('연령대', s.age, ['#818CF8', '#6366F1', '#4F46E5', '#4338CA']);
  html += block('지역', s.region, ['#14B8A6', '#0EA5E9', '#06B6D4', '#0891B2', '#94A3B8']);
  document.getElementById('psStats').innerHTML = html;
}}

function genParticipantInsight() {{
  if (!IS_LOCAL) {{ showToast('⚠️ 분석은 로컬 서버에서만 가능합니다', 3000); return; }}
  var idx = _detailIdx;
  if (idx === null || idx === undefined) return;
  var m = MARKETS_DATA[idx];
  if (!m) return;
  var btn = document.getElementById('psInsightBtn');
  btn.disabled = true; btn.textContent = '분석 중... (~15초)';
  fetch('/api/participant-insight', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ question: m.question, options: m.options || [], guide: m.audience_insight_guide || '' }})
  }}).then(function(r) {{ return r.json(); }}).then(function(res) {{
    btn.disabled = false; btn.textContent = '🤖 AI 참여자 분석 리포트 생성';
    if (!res.ok) {{ showToast('⚠️ ' + (res.message || '분석 실패'), 3000); return; }}
    var el = document.getElementById('psInsight');
    el.innerHTML = '<b>🤖 AI 참여자 인사이트</b><br>' + (res.insight || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    el.style.display = 'block';
  }}).catch(function(e) {{
    btn.disabled = false; btn.textContent = '🤖 AI 참여자 분석 리포트 생성';
    showToast('⚠️ 서버 연결 실패', 3000);
  }});
}}

function closeDetailModal(e) {{
  if (e && e.target !== document.getElementById('detailBackdrop')) return;
  document.getElementById('detailBackdrop').classList.remove('open');
  _detailIdx = null;
}}

function publishMarket() {{
  var idx = _detailIdx;
  if (idx === null || idx === undefined) return;
  var m = MARKETS_DATA[idx];
  if (!m) return;
  var opts = document.getElementById('d_options').value.split('\\n').map(function(s) {{ return s.trim(); }}).filter(Boolean);
  var tags = document.getElementById('d_tags').value.split(',').map(function(s) {{ return s.trim(); }}).filter(Boolean);
  var edited = Object.assign({{}}, m, {{
    question: document.getElementById('d_question').value.trim(),
    options: opts,
    trend_tags: tags,
    content_insight: document.getElementById('d_insight').value.trim(),
    resolution_criteria: document.getElementById('d_resolution').value.trim(),
    push_notification_headline: document.getElementById('d_push').value.trim()
  }});
  MARKETS_DATA[idx] = edited;
  if (!IS_LOCAL) {{ showToast('⚠️ 발행은 로컬 서버(python server.py)에서만 가능합니다', 3000); return; }}
  var btn = document.getElementById('publishBtn');
  btn.disabled = true; btn.textContent = '발행 중...';
  fetch('/api/publish', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(edited)
  }}).then(function(r) {{ return r.json(); }}).then(function(res) {{
    btn.disabled = false; btn.textContent = '🚀 최종 발행/배포';
    if (res.ok) {{
      showToast('🚀 발행 완료! 참여자 분석이 활성화됐어요 (총 ' + res.total + '건)');
      // 발행 즉시 '진행중'으로 전환 → 참여자 통계/AI 리포트 활성화
      if (PUBLISHED_QUESTIONS.indexOf(edited.question) === -1) PUBLISHED_QUESTIONS.push(edited.question);
      renderParticipantSection(edited);
    }}
    else {{ showToast('⚠️ 발행 실패'); }}
  }}).catch(function(e) {{ btn.disabled = false; btn.textContent = '🚀 최종 발행/배포'; showToast('⚠️ 서버 연결 실패'); }});
}}

// ── 수동 발행 / 자동 키워드 ──────────────────────────
function generateFromKeyword(keyword, btn) {{
  keyword = (keyword || '').trim();
  if (!keyword) {{ showToast('키워드를 입력하세요'); return; }}
  if (!IS_LOCAL) {{ showToast('⚠️ AI 생성은 로컬 서버(python server.py)에서만 가능합니다', 3000); return; }}
  var mainBtn = document.getElementById('manualGenBtn');
  if (btn) {{ btn.disabled = true; btn.textContent = '생성 중...'; }}
  if (mainBtn) mainBtn.disabled = true;
  showToast('🤖 "' + keyword + '" 실시간 조사 중... (~30초)', 6000);
  fetch('/api/generate', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{keyword: keyword}})
  }}).then(function(r) {{ return r.json(); }}).then(function(res) {{
    if (res.ok) {{
      showToast('✅ ' + res.count + '개 생성됨! 대시보드로 이동합니다...', 2000);
      setTimeout(function() {{ window.location.reload(); }}, 1800);
    }} else {{
      showToast('⚠️ ' + (res.message || '생성 실패'), 3500);
      if (btn) {{ btn.disabled = false; btn.textContent = '즉시 마켓 생성'; }}
      if (mainBtn) mainBtn.disabled = false;
    }}
  }}).catch(function(e) {{
    showToast('⚠️ 서버 연결 실패 (python server.py 확인)', 3500);
    if (btn) {{ btn.disabled = false; btn.textContent = '즉시 마켓 생성'; }}
    if (mainBtn) mainBtn.disabled = false;
  }});
}}

function genFromAuto(i, btn) {{
  var k = AUTO_KEYWORDS[i];
  if (k) generateFromKeyword(k.keyword, btn);
}}

function renderAutoKeywords() {{
  var box = document.getElementById('autoKeywordList');
  var cnt = document.getElementById('autoKwCount');
  if (!box) return;
  if (!AUTO_KEYWORDS || !AUTO_KEYWORDS.length) {{
    box.innerHTML = '<p class="empty-state">자동 키워드 없음 (동기화 후 표시)</p>';
    return;
  }}
  if (cnt) cnt.textContent = '(' + AUTO_KEYWORDS.length + '개)';
  box.innerHTML = AUTO_KEYWORDS.map(function(k, i) {{
    return '<div class="kw-row">' +
      '<span class="kw-domain">' + (k.domain || '') + '</span>' +
      '<span class="kw-name">' + (k.keyword || '') + '</span>' +
      '<button class="kw-gen-btn" onclick="genFromAuto(' + i + ', this)">즉시 마켓 생성</button>' +
      '</div>';
  }}).join('');
}}

// ── 제외(거절) 이력 탭 ───────────────────────────────
var REASON_LABELS = ['이미 지난 이슈', '결과가 이미 알려진 내용', '마켓 매력도 낮음', '타겟과 맞지 않음', '선택지가 부적절', '정보가 부정확함', '민감한 주제', '유사 마켓 이미 존재'];
var _rejectsCache = REJECTS_DATA || [];
var _lastImprove = '';

function loadRejects() {{
  if (IS_LOCAL) {{
    fetch('/api/rejects').then(function(r) {{ return r.json(); }}).then(function(list) {{
      _rejectsCache = list || [];
      renderRejects(_rejectsCache);
    }}).catch(function(e) {{ renderRejects(_rejectsCache); }});
  }} else {{
    renderRejects(_rejectsCache);
  }}
}}

function renderRejects(list) {{
  var total = document.getElementById('rejectTotal');
  if (total) total.textContent = list.length ? ('누적 ' + list.length + '건') : '';
  var listCount = document.getElementById('rejectListCount');
  if (listCount) listCount.textContent = '(' + list.length + '건)';

  // 사유 카테고리 집계 (순수 계산 — API 호출 없음)
  var counts = {{}};
  REASON_LABELS.forEach(function(lbl) {{ counts[lbl] = 0; }});
  list.forEach(function(r) {{
    (r.rejected_reasons || []).forEach(function(reason) {{
      if (counts.hasOwnProperty(reason)) counts[reason]++;
    }});
  }});
  var pills = REASON_LABELS.filter(function(lbl) {{ return counts[lbl] > 0; }})
    .sort(function(a, b) {{ return counts[b] - counts[a]; }})
    .map(function(lbl) {{ return '<span class="reject-count-pill">' + lbl + ' <b>' + counts[lbl] + '</b></span>'; }})
    .join('');
  var cbox = document.getElementById('rejectCounts');
  if (cbox) cbox.innerHTML = pills || '<span style="font-size:12px;color:#94A3B8">집계할 사유 없음</span>';

  // 목록
  var box = document.getElementById('rejectList');
  if (!box) return;
  if (!list.length) {{ box.innerHTML = '<p class="empty-state">제외된 마켓이 없습니다</p>'; return; }}
  box.innerHTML = list.map(function(r) {{
    var reasons = (r.rejected_reasons || []).map(function(x) {{ return '<span class="rj-reason">' + x + '</span>'; }}).join('');
    var memo = r.rejected_memo ? '<span class="rj-memo">memo: ' + r.rejected_memo + '</span>' : '';
    var date = r.rejected_at ? '<span class="rj-date">' + r.rejected_at + '</span>' : '';
    return '<div class="rj-row">' +
      '<div class="rj-q">' + (r.question || '') + '</div>' +
      '<div class="rj-reasons">' + reasons + ' ' + memo + date + '</div>' +
      '</div>';
  }}).join('');
}}

function analyzeRejects() {{
  if (!IS_LOCAL) {{ showToast('⚠️ 분석은 로컬 서버(python server.py)에서만 가능합니다', 3000); return; }}
  var btn = document.getElementById('analyzeBtn');
  btn.disabled = true; btn.textContent = '분석 중... (~20초)';
  showToast('🤖 거절 패턴 분석 중...', 5000);
  fetch('/api/analyze-rejects', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: '{{}}' }})
    .then(function(r) {{ return r.json(); }}).then(function(res) {{
      btn.disabled = false; btn.textContent = '🤖 거절 패턴 분석 & 프롬프트 개선안 도출';
      if (!res.ok) {{ showToast('⚠️ ' + (res.message || '분석 실패'), 3500); return; }}
      var a = res.analysis || {{}};
      var issues = (a.top_issues || []).map(function(s) {{ return '<li>' + s + '</li>'; }}).join('');
      _lastImprove = (a.prompt_improvements || []).join('\\n\\n');
      var html = '<h4>📋 진단 (거절 ' + res.count + '건 기준)</h4>' +
        '<div class="diag">' + (a.diagnosis || '') + '</div>' +
        '<h4>⚠️ 주요 문제 패턴</h4><ul>' + issues + '</ul>' +
        '<h4>✏️ 프롬프트 개선안 (자동 적용 안 함 · 검토 후 수동 반영)</h4>' +
        '<div class="improve-box"><button class="copy-btn" onclick="copyImprove(this)">복사</button>' +
        _lastImprove.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>';
      var rbox = document.getElementById('analyzeResult');
      rbox.innerHTML = html; rbox.style.display = 'block';
      showToast('✅ 분석 완료 — 자동 적용하지 않습니다. 검토 후 반영하세요', 3500);
    }}).catch(function(e) {{
      btn.disabled = false; btn.textContent = '🤖 거절 패턴 분석 & 프롬프트 개선안 도출';
      showToast('⚠️ 서버 연결 실패', 3000);
    }});
}}

function copyImprove(btn) {{
  if (navigator.clipboard) navigator.clipboard.writeText(_lastImprove);
  btn.textContent = '복사됨';
  setTimeout(function() {{ btn.textContent = '복사'; }}, 1500);
}}

// ── 초기화 ───────────────────────────────────────────
function init() {{
  try {{
    initSyncBtn();
  }} catch(e) {{ console.warn('initSyncBtn error:', e); }}

  // 잠금 상태 복원 (로컬에선 서버 우선, Vercel에선 localStorage)
  try {{
    if (IS_LOCAL) {{
      loadLocksFromServer();
    }} else {{
      restoreLockUI();
    }}
  }} catch(e) {{ console.warn('lock restore error:', e); }}

  // 거절 상태 복원 (로컬은 서버 우선, Vercel은 localStorage)
  try {{
    if (IS_LOCAL) loadRejectsFromServer();
    else restoreRejectedUI();
  }} catch(e) {{ console.warn('reject restore error:', e); }}

  // 자동 키워드 리스트 렌더
  try {{ renderAutoKeywords(); }} catch(e) {{ console.warn('auto keyword render error:', e); }}

  // 타겟 분포가 고정 높이를 넘으면 '더보기' 버튼 노출
  try {{
    var tp = document.getElementById('targetPills');
    var tbtn = document.getElementById('targetMoreBtn');
    if (tp && tbtn && tp.scrollHeight > tp.clientHeight + 4) tbtn.style.display = 'inline-block';
  }} catch(e) {{ console.warn('target more btn error:', e); }}

  // 히스토리 첫 날짜 자동 로드
  try {{
    var sel = document.getElementById('historyDateSelect');
    if (sel && sel.value) {{
      loadHistoryDate(sel.value);
    }}
  }} catch(e) {{ console.warn('history load error:', e); }}
}}

// DOMContentLoaded 이후 초기화 (이미 로드됐으면 즉시 실행)
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', init);
}} else {{
  init();
}}
</script>
</body>
</html>"""


def build_dashboard():
    issues, markets = load_data()
    history = load_history()

    if not issues and not markets:
        print("수집된 데이터가 없습니다.")
        return

    html = generate_html(issues, markets, history)
    output_path = "dashboard.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    # Vercel 배포용 index.html 동기화
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"대시보드 생성 완료 → {output_path} / index.html")
    return output_path


if __name__ == "__main__":
    build_dashboard()
