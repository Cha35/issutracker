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
from datetime import datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCKED_PATH = os.path.join(BASE_DIR, "locked_markets.json")
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
    return jsonify({"ok": True, "message": "동기화 시작됨 (~2분 소요)"})


@app.route("/api/sync/status")
def sync_status():
    return jsonify(SYNC_STATUS)


@app.route("/api/sync/log")
def sync_log():
    return jsonify({"log": SYNC_STATUS.get("last_log", "")})


if __name__ == "__main__":
    print("\n" + "="*45)
    print("  폴리볼 이슈 수집 로컬 서버 시작")
    print("  접속: http://localhost:8080")
    print("="*45 + "\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
