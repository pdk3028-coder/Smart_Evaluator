from flask import Flask, send_from_directory
from flask_cors import CORS
import db
from routes import api_bp
import os

app = Flask(__name__, static_folder="static", static_url_path="")

# CORS 설정
CORS(app, resources={r"/api/*": {"origins": "*"}})

# API 블루프린트 등록
app.register_blueprint(api_bp, url_prefix="/api")

# React 정적 파일 직접 서빙 및 SPA 라우팅 지원
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_static(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")

# DB 초기화
with app.app_context():
    db.init_db()

if __name__ == "__main__":
    # 로컬 개발 서버 실행 (포트 8000)
    app.run(host="0.0.0.0", port=8000, debug=True)
