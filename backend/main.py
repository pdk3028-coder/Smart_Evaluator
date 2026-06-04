import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import db
from routes import router
import os

app = FastAPI(title="Smart Evaluator API", description="동료사원평가 시스템용 API 백엔드")

# CORS 미들웨어 설정
# React 프론트엔드가 다른 포트(예: 3000, 5173 등)에서 원활하게 요청을 보낼 수 있도록 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실무 환경에 맞춰 특정 도메인으로 축소 가능
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(router, prefix="/api")

# React 정적 파일 마운트 (dist -> static)
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
else:
    @app.get("/")
    def read_root():
        return {"message": "스마트 평가기 백엔드 API 서버가 정상적으로 실행 중입니다. (정적 파일 폴더 static 없음)"}

@app.on_event("startup")
def on_startup():
    """서버가 시작될 때 SQLite 데이터베이스 스키마 마이그레이션 및 초기화를 수행합니다."""
    db.init_db()

if __name__ == "__main__":
    # 개발 서버 실행 (포트 8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
