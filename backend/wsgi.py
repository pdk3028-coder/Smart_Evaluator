from a2wsgi import ASGIMiddleware
from main import app

# a2wsgi를 사용하여 ASGI (FastAPI) 애플리케이션을 WSGI 애플리케이션으로 변환합니다.
# PythonAnywhere는 기본적으로 WSGI 웹 앱 환경을 제공하므로 이 어댑터를 거쳐 배포합니다.
wsgi_app = ASGIMiddleware(app)
