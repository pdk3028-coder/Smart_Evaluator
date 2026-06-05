import sys
import os

# PythonAnywhere 배포 환경에서 백엔드 경로 탐색 보장
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

from main import app as application

# PythonAnywhere의 기존 WSGI 설정(wsgi_app 임포트)과의 호환성을 보장합니다.
wsgi_app = application

