import json
import os
from datetime import datetime
from collections import Counter
from config import CATEGORY_LABELS

MARKET_TYPE_KO = {
    "prediction": "예측",
    "vote": "투표",
    "ranking": "랭킹 예측",
    "numeric": "수치 예측",
    "timing": "타이밍 예측",
}

MARKET_TYPE_COLOR = {
    "prediction": "#4F46E5",
    "vote": "#059669",
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
    rationale = m.get('rationale', '').replace('<', '&lt;').replace('>', '&gt;')
    title_attr = issue_title.replace('"', '&quot;')

    return f"""
    <div class="market-card" data-type="{mtype}" data-score="{score}" data-sourcetype="{source_type}" data-idx="{idx}" id="mcard-{idx}">
      <div class="locked-ribbon">🔒 잠금</div>
      <div class="card-header" style="border-left: 4px solid {color}">
        <span class="type-badge" style="background:{color}">{type_ko}</span>
        <span class="target-badge" style="background:{target_color}">{target}</span>
        <span class="score">{stars}</span>
        <button class="lock-btn" onclick="toggleLock({idx}, this)" title="잠금 시 동기화해도 유지됨">🔓</button>
      </div>
      <div class="card-body">
        <p class="question">{question}</p>
        <div class="options">{options_html}</div>
        <div class="source-row">
          <span class="source-title" title="{title_attr}">{short_title}</span>
          {link_html}
        </div>
        <p class="rationale">{rationale}</p>
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

    # 현재 마켓 데이터 (잠금 저장용)
    markets_for_js = [
        {
            "issue_title": m.get("issue_title", ""),
            "market_type": m.get("market_type", ""),
            "question": m.get("question", ""),
            "options": m.get("options", []),
            "category": m.get("category", ""),
            "rationale": m.get("rationale", ""),
            "target_audience": m.get("target_audience", "공통"),
            "marketability_score": m.get("marketability_score", 0),
            "source_link": m.get("source_link", ""),
            "source_type": m.get("source_type", "issue"),
        }
        for m in markets
    ]

    history_data_js = json.dumps(history_for_js, ensure_ascii=False)
    markets_data_js = json.dumps(markets_for_js, ensure_ascii=False)
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
  select {{ background: white; border: 1px solid #E2E8F0; color: #374151; padding: 6px 12px; border-radius: 8px; font-size: 13px; cursor: pointer; }}
  .cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
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
  .card-body {{ padding: 14px 16px; }}
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
        <div>{target_pills}</div>
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
      </div>
      <div class="filter-row">{filter_buttons}</div>
      <div class="cards-grid" id="cardsGrid">{market_cards}</div>
    </div>
  </div>
</div>

<div id="page-history" class="page">
  <div class="container">
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

<div class="toast" id="toast"></div>

<script>
// ── 데이터 ──────────────────────────────────────────
const HISTORY_DATA = {history_data_js};
const MARKETS_DATA = {markets_data_js};
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
}}

// ── 필터 / 정렬 ──────────────────────────────────────
function filterCards(type, btn) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.market-card').forEach(function(card) {{
    card.classList.toggle('hidden', type !== 'all' && card.dataset.type !== type);
  }});
}}
function filterCreative(btn) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.market-card').forEach(function(card) {{
    card.classList.toggle('hidden', card.dataset.sourcetype !== 'creative');
  }});
}}
function filterLocked(btn) {{
  document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.market-card').forEach(function(card) {{
    card.classList.toggle('hidden', !card.classList.contains('locked'));
  }});
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
  document.getElementById('syncStatus').textContent = '수집 중... (~2분 소요)';
  showToast('🔄 동기화 시작! 약 2분 후 자동으로 새로고침됩니다', 4000);

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
          ' onchange="toggleApplied(\'' + date + '\',' + i + ',this.checked)"' +
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
