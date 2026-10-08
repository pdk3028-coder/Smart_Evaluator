from flask import Flask, request, send_from_directory
from flask_cors import CORS
import db
from routes import api_bp
import os

app = Flask(__name__, static_folder="static", static_url_path="")

# CORS 설정
CORS(app, resources={r"/api/*": {"origins": "*"}})

# API 블루프린트 등록
app.register_blueprint(api_bp, url_prefix="/api")

@app.after_request
def prevent_stale_app_cache(response):
    # The entry document must always load the current hashed frontend bundle.
    # API responses contain live evaluation data and must not be reused either.
    if response.mimetype == "text/html" or request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers.pop("ETag", None)
        response.headers.pop("Last-Modified", None)
    return response

# React 정적 파일 직접 서빙 및 SPA 라우팅 지원
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_static(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        # Ignore validators from an older cached entry document: return fresh HTML.
        return send_from_directory(app.static_folder, "index.html", conditional=False, etag=False)

@app.route("/index.html")
def serve_entry_document():
    return serve_static("")

# DB 초기화
with app.app_context():
    from migrations import ensure_ready
    ensure_ready(db.DB_PATH)

if __name__ == "__main__":
    # 로컬 개발 서버 실행 (포트 8000)
    app.run(host="0.0.0.0", port=8000, debug=True)
