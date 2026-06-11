"""
폴리볼 이슈 수집 로컬 서버
실행: python server.py
접속: http://localhost:8080
"""
from flask import Flask, send_file, request, jsonify, make_response
import json
import os
import subprocess
import threading
import hashlib
from datetime import datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCKED_PATH = os.path.join(BASE_DIR, "locked_markets.json")
REJECTED_PATH = os.path.join(BASE_DIR, "rejected_markets.json")
PUBLISHED_PATH = os.path.join(BASE_DIR, "published_markets.json")
DRAFTS_PATH = os.path.join(BASE_DIR, "market_drafts.json")
KEYWORDS_PATH = os.path.join(BASE_DIR, "collected_keywords.json")
SYNC_STATUS = {
    "running": False,
    "last": "없음",
    "last_log": "",
    "last_result": "대기 중"
}


@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(BASE_DIR, "dashboard.html")))
    # 브라우저 캐시 방지 - 항상 최신 파일 읽도록
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/api/locks", methods=["GET", "POST"])
def locks():
    if request.method == "POST":
        data = request.get_json(force=True)
        with open(LOCKED_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True, "count": len(data)})
    if os.path.exists(LOCKED_PATH):
        with open(LOCKED_PATH, encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])


@app.route("/api/sync", methods=["POST"])
def sync():
    if SYNC_STATUS["running"]:
        return jsonify({"ok": False, "message": "이미 동기화 중입니다."})

    def run_sync():
        SYNC_STATUS["running"] = True
        SYNC_STATUS["last_result"] = "실행 중..."
        SYNC_STATUS["last_log"] = ""
        try:
            python = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
            result = subprocess.run(
                [python, "run.py"],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            log = result.stdout + result.stderr
            SYNC_STATUS["last_log"] = log[-3000:] if len(log) > 3000 else log
            if result.returncode == 0:
                SYNC_STATUS["last_result"] = "성공"
                print("\n[동기화 완료]")
                print(log[-1000:])
            else:
                SYNC_STATUS["last_result"] = "오류"
                print("\n[동기화 오류]")
                print(log[-2000:])
        except Exception as e:
            SYNC_STATUS["last_result"] = f"예외: {e}"
            SYNC_STATUS["last_log"] = str(e)
            print(f"\n[동기화 예외] {e}")
        finally:
            SYNC_STATUS["running"] = False
            SYNC_STATUS["last"] = datetime.now().strftime("%H:%M")

    threading.Thread(target=run_sync, daemon=True).start()
    return jsonify({"ok": True, "message": "동기화 시작됨 (pro 모델 생성, ~4-5분 소요)"})


@app.route("/api/sync/status")
def sync_status():
    return jsonify(SYNC_STATUS)


@app.route("/api/rejects", methods=["GET", "POST"])
def rejects():
    if request.method == "POST":
        data = request.get_json(force=True)
        # 기존 거절 목록 불러와서 누적
        existing = []
        if os.path.exists(REJECTED_PATH):
            with open(REJECTED_PATH, encoding="utf-8") as f:
                existing = json.load(f)
        # 동일 question 중복 방지
        questions = {r.get("question", "") for r in existing}
        if data.get("question", "") not in questions:
            existing.append(data)
            with open(REJECTED_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True, "total": len(existing)})
    # GET: 거절 목록 반환
    if os.path.exists(REJECTED_PATH):
        with open(REJECTED_PATH, encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify([])


@app.route("/api/sync/log")
def sync_log():
    return jsonify({"log": SYNC_STATUS.get("last_log", "")})


@app.route("/api/keywords")
def keywords():
    """하이브리드 엔진이 추출한 실시간 자동 키워드 목록."""
    if os.path.exists(KEYWORDS_PATH):
        with open(KEYWORDS_PATH, encoding="utf-8") as f:
            items = json.load(f)
        # 프론트에 필요한 최소 정보만
        return jsonify([{"keyword": it.get("keyword", ""), "domain": it.get("domain", "")} for it in items])
    return jsonify([])


@app.route("/api/generate", methods=["POST"])
def generate():
    """관리자 수동 키워드 → google_search 실시간 조사 → 마켓 초안 생성."""
    import engine
    from dashboard import build_dashboard

    data = request.get_json(force=True)
    keyword = (data.get("keyword") or "").strip()
    if not keyword:
        return jsonify({"ok": False, "message": "키워드를 입력하세요."})

    try:
        new_markets = engine.generate_from_manual_keyword(keyword)
    except Exception as e:
        return jsonify({"ok": False, "message": f"생성 실패: {e}"})

    if not new_markets:
        return jsonify({"ok": False, "message": "생성된 마켓이 없습니다. 다른 키워드를 시도하세요."})

    # 기존 초안 로드 → 신규를 앞에 붙여 저장 (중복 질문 제외)
    markets = []
    if os.path.exists(DRAFTS_PATH):
        with open(DRAFTS_PATH, encoding="utf-8") as f:
            markets = json.load(f)
    existing_q = {m.get("question", "") for m in markets}
    added = [m for m in new_markets if m.get("question", "") not in existing_q]
    markets = added + markets
    with open(DRAFTS_PATH, "w", encoding="utf-8") as f:
        json.dump(markets, f, ensure_ascii=False, indent=2)

    try:
        build_dashboard()
    except Exception as e:
        print(f"[generate] 대시보드 재빌드 실패: {e}")

    return jsonify({"ok": True, "count": len(added), "keyword": keyword})


def _mock_participant_stats(question):
    """⚠️ 데모용 목업 — 실제 유저 DB 연결 지점. 질문 기반 결정적 분포(같은 마켓이면 항상 동일)."""
    h = hashlib.md5((question or "x").encode("utf-8")).hexdigest()
    n = [int(h[i:i + 2], 16) for i in range(0, 24, 2)]  # 12개 바이트
    total = 300 + n[0] * 12
    male = 35 + n[1] % 31
    raw_age = [n[2] + 5, n[3] + 22, n[4] + 14, n[5] + 5]
    sa = sum(raw_age)
    age = [round(x * 100 / sa) for x in raw_age]
    age[-1] = 100 - sum(age[:-1])
    raw_reg = [n[6] + 25, n[7] + 20, n[8] + 8, n[9] + 6, n[10] + 10]
    sr = sum(raw_reg)
    reg = [round(x * 100 / sr) for x in raw_reg]
    reg[-1] = 100 - sum(reg[:-1])
    return {
        "total": total,
        "gender": {"남성": male, "여성": 100 - male},
        "age": {"10대": age[0], "20대": age[1], "30대": age[2], "40대+": age[3]},
        "region": {"서울": reg[0], "경기/인천": reg[1], "부산/경남": reg[2], "대구/경북": reg[3], "기타": reg[4]},
        "mock": True,
    }


@app.route("/api/participants")
def participants():
    """마켓 참여자 통계 (현재 데모 목업 — 실 유저 DB 연결 지점)."""
    q = request.args.get("q", "")
    return jsonify(_mock_participant_stats(q))


@app.route("/api/participant-insight", methods=["POST"])
def participant_insight():
    """참여자 통계 → Gemini 해석 리포트 (버튼 클릭 시에만 1회 호출)."""
    import engine
    data = request.get_json(force=True)
    q = (data.get("question") or "").strip()
    if not q:
        return jsonify({"ok": False, "message": "질문 정보가 없습니다."})
    stats = _mock_participant_stats(q)
    try:
        insight = engine.generate_participant_insight(q, data.get("options", []), stats, data.get("guide", ""))
    except Exception as e:
        return jsonify({"ok": False, "message": f"분석 실패: {e}"})
    return jsonify({"ok": True, "insight": insight, "stats": stats})


@app.route("/api/analyze-rejects", methods=["POST"])
def analyze_rejects():
    """거절 이력 패턴 분석 (관리자가 버튼 클릭 시에만 1회 호출)."""
    import engine
    if not os.path.exists(REJECTED_PATH):
        return jsonify({"ok": False, "message": "분석할 거절 이력이 없습니다."})
    with open(REJECTED_PATH, encoding="utf-8") as f:
        rejects = json.load(f)
    if not rejects:
        return jsonify({"ok": False, "message": "분석할 거절 이력이 없습니다."})
    try:
        result = engine.analyze_rejections(rejects)
    except Exception as e:
        return jsonify({"ok": False, "message": f"분석 실패: {e}"})
    return jsonify({"ok": True, "count": len(rejects), "analysis": result})


@app.route("/api/publish", methods=["POST"])
def publish():
    """검수 완료 마켓 발행 → published_markets.json 누적 (실제 배포 API 연결 지점)."""
    data = request.get_json(force=True)
    published = []
    if os.path.exists(PUBLISHED_PATH):
        with open(PUBLISHED_PATH, encoding="utf-8") as f:
            published = json.load(f)
    data["published_at"] = datetime.now().isoformat()
    published.append(data)
    with open(PUBLISHED_PATH, "w", encoding="utf-8") as f:
        json.dump(published, f, ensure_ascii=False, indent=2)
    # 발행 상태를 대시보드에 반영 (PUBLISHED_QUESTIONS 갱신 — 다음 로드 시 '진행중' 표시)
    try:
        from dashboard import build_dashboard
        build_dashboard()
    except Exception as e:
        print(f"[publish] 대시보드 재빌드 실패: {e}")
    return jsonify({"ok": True, "total": len(published)})


if __name__ == "__main__":
    print("\n" + "="*45)
    print("  폴리볼 이슈 수집 로컬 서버 시작")
    print("  접속: http://localhost:8080")
    print("="*45 + "\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
