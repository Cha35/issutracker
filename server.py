"""
폴리볼 이슈 수집 로컬 서버
실행: python server.py
접속: http://localhost:8080
"""
from flask import Flask, send_file, request, jsonify
import json
import os
import subprocess
import threading

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCKED_PATH = os.path.join(BASE_DIR, "locked_markets.json")
SYNC_STATUS = {"running": False, "last": "없음"}


@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "dashboard.html"))


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
        python = os.path.join(BASE_DIR, "venv", "Scripts", "python.exe")
        subprocess.run([python, "run.py"], cwd=BASE_DIR, capture_output=True)
        SYNC_STATUS["running"] = False
        from datetime import datetime
        SYNC_STATUS["last"] = datetime.now().strftime("%H:%M")

    threading.Thread(target=run_sync, daemon=True).start()
    return jsonify({"ok": True, "message": "동기화 시작됨 (~2분 소요)"})


@app.route("/api/sync/status")
def sync_status():
    return jsonify(SYNC_STATUS)


if __name__ == "__main__":
    print("\n" + "="*45)
    print("  폴리볼 이슈 수집 로컬 서버 시작")
    print("  접속: http://localhost:8080")
    print("="*45 + "\n")
    app.run(host="0.0.0.0", port=8080, debug=False)
