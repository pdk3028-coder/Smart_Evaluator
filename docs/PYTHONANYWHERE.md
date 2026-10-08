# SmartEvaluator PythonAnywhere 적용 준비

확인한 환경:

- PythonAnywhere 대상 계정: `SmartEvaluator` (사용자가 제공한 관리 페이지 주소 기준)
- GitHub: <https://github.com/pdk3028-coder/Smart_Evaluator>
- 배포 기준 브랜치: `master`
- 수정 기준 커밋: `5b7ae27581e5861dadd26eda6f01273fa0b0733f`
- 로컬 수정본에는 빌드된 `backend/static`이 포함된다.

2026-10-07 대상 계정의 설정을 확인하고 코드·DB 백업, 복제본 시험, 운영 DB 이전, GitHub master 반영 및 서비스 재시작을 완료했다. 실제 결과와 백업 위치는 [운영 적용 기록](DEPLOYMENT_COMPLETE.md)에 정리했다. 운영 설정은 아래와 같다.

| 설정 | 확인한 값 |
| --- | --- |
| 도메인 | `SmartEvaluator.pythonanywhere.com` |
| Source code / Working directory | `/home/SmartEvaluator/backend` |
| 프로젝트의 `.git` 위치 | `/home/SmartEvaluator/.git` (운영 remote·커밋은 별도 확인 필요) |
| DB | `/home/SmartEvaluator/employees.db` (`db.py`의 Linux 경로 계산과 실제 파일 존재 확인) |
| Python | `3.10` |
| Virtualenv | `/home/SmartEvaluator/.virtualenvs/myenv` |
| WSGI | `/var/www/smartevaluator_pythonanywhere_com_wsgi.py` |
| WSGI import | `from wsgi import wsgi_app as application` |
| 정적 경로 | `/assets/`, `/icons.svg`, `/favicon.svg`가 `backend/static` 아래 파일·디렉터리를 가리킴. 첫 화면 `/`는 Flask가 제공한다. |

## 화면 캐시 설정 (2026-10-08)

북마크 접속 시 이전 화면이 재사용되는 문제를 방지하기 위해 HTML 및 `/api/` 응답에 `Cache-Control: no-store, no-cache, max-age=0, must-revalidate`를 적용한다. `/`와 `/index.html`은 이전 HTML의 조건부 요청에도 최신 문서를 200으로 반환한다. 파일명에 해시가 들어간 `/assets/` 파일은 기존처럼 직접 제공한다.

PythonAnywhere Web > Static files에 `/` → `/home/SmartEvaluator/backend/static` 매핑이 있으면 **해당 매핑만 제거**하고 Reload한다. 파일이나 DB를 삭제하는 작업이 아니다. 루트 매핑이 남으면 첫 화면이 Flask를 우회하므로 캐시 정책이 적용되지 않는다. 이후 배포에서도 루트 매핑을 다시 추가하지 않는다.

배포 후 `/`, `/index.html`, `/api/admin/rounds`의 상태 200 및 `Cache-Control`을 확인하고 `/assets/` 로딩을 확인한다. 배포 전에 PC에 이미 저장된 화면은 한 번 `Ctrl+Shift+R`로 갱신해야 할 수 있다. 이후 방문에는 새 정책이 적용된다. DB 이전이나 로그인 정보 초기화는 필요하지 않다.

계정 홈 자체가 체크아웃 루트이므로 홈 디렉터리를 통째로 패키징하지 않는다. 코드·정적 파일·WSGI 및 DB를 필요한 범위로 백업하고 `.ssh`, 계정 설정, 가상환경, 명부를 코드 배포 패키지에 섞지 않는다.

## 먼저 확인할 설정

`SmartEvaluator`로 로그인한 뒤 **Web** 탭에서 다음 값을 기록한다.

1. 서비스 도메인
2. Code의 **Source code**, **Working directory**, **WSGI configuration file**
3. **Virtualenv** 경로와 Python 버전
4. **Static files**의 URL·경로 매핑

현재 WSGI는 `/home/SmartEvaluator/backend`를 Python import 경로에 넣고 `wsgi_app`을 불러온다. 운영 `db.py`의 Linux 기본 DB 경로는 **프로젝트 루트/employees.db**이며 `/home/SmartEvaluator/employees.db` 파일이 존재한다. 앞으로 배포 시 이 절대경로를 환경변수로 명시한다.

Source code와 DB 위치가 확인되면 Bash 콘솔에서 아래 읽기 전용 확인을 수행한다.

```sh
cd /home/SmartEvaluator
git remote -v
git status --short
git rev-parse HEAD
```

운영 체크아웃에 로컬 변경이 있으면 먼저 보관하고 업데이트 내용을 비교한다. `git reset --hard`, `git clean`, 명부 초기화 또는 DB 파일 교체로 해결하지 않는다.

## GitHub 반영과 운영 적용은 별도 단계

수정 브랜치를 검토한 뒤 GitHub에 반영한다. 원본 DB, 이전 후 DB, 명부, 백업은 GitHub에 올리지 않는다. 이번 수정은 DB 버전 변경을 포함하므로 **운영 서버에서 git pull 후 바로 Reload만 누르면 안 된다.** 새 버전은 이전하지 않은 DB를 발견하면 시작을 거부한다. 먼저 운영 쓰기를 멈추고 DB를 백업·검증·이전해야 한다.

## 구버전 서버까지 멈추는 점검 방법

기존 코드는 `.maintenance` 파일을 확인하지 않는다. PythonAnywhere의 WSGI 설정을 임시 점검 응답으로 바꾸고 **Reload**해 기존 앱의 모든 요청이 끝나게 하는 방법을 사용할 수 있다. 별도 Task·Console에서 DB를 쓰는 프로그램도 중지해야 한다.

1. 실제 WSGI 파일과 현재 체크아웃의 코드·정적 파일·설정을 비공개 위치에 보관한다.
2. WSGI를 아래 임시 응답으로 바꾸고 Web 탭에서 Reload한다. 이 코드는 Flask나 DB를 import하지 않는다.

```python
def application(environ, start_response):
    body = '자료 보존을 위한 서비스 점검 중입니다. 잠시 후 다시 접속해 주세요.'.encode('utf-8')
    start_response('503 Service Unavailable', [
        ('Content-Type', 'text/plain; charset=utf-8'),
        ('Content-Length', str(len(body))),
        ('Retry-After', '600'),
        ('Cache-Control', 'no-store'),
    ])
    return [body]
```

3. Reload 완료 후 실제 서비스의 `/api/common/upload-status`가 503을 반환하는지 확인한다. WSGI를 우회하는 다른 앱·작업이 운영 DB를 쓰지 않는지도 확인한다. Static files 매핑은 정적 파일을 별도로 제공하므로 첫 화면만 보고 점검 여부를 판단하지 않는다.
4. 이 상태에서 검토된 GitHub 수정본을 반영하고 [일반 적용 절차](DEPLOYMENT.md)의 `backup`, `dry-run`, `migrate --maintenance`, `inspect`를 운영 가상환경 Python으로 실행한다. 운영 가상환경 Python은 `/home/SmartEvaluator/.virtualenvs/myenv/bin/python`이다. 대상 DB는 `/home/SmartEvaluator/employees.db`로 지정한다. 로그와 백업은 프로젝트의 공개 정적 경로 밖에 보관한다. 새 이전 도구가 배치된 뒤 복제 검증에 사용할 명령은 다음과 같다.

```sh
cd /home/SmartEvaluator
/home/SmartEvaluator/.virtualenvs/myenv/bin/python backend/manage_db.py dry-run --db /home/SmartEvaluator/employees.db
```

PythonAnywhere 공식 문서에 따르면 Reload는 현재 워커의 요청이 끝난 뒤 기존 워커를 정지하고 새 코드로 다시 시작한다. 이를 이용해 이전 중 구버전 앱이 DB를 다시 쓰는 것을 막는다. Reload 자체가 DB 백업이나 이전을 수행해주지는 않는다.

## 새 앱으로 전환

이전 검증에 성공한 뒤 실제 WSGI 파일을 복구하고, 앱을 import하기 전에 DB 경로를 명시한다. 기존 WSGI의 필요 설정은 유지한다. 예시:

```python
import os
import sys

backend_path = '/home/SmartEvaluator/backend'
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

os.environ['SMART_EVALUATOR_DB'] = '/home/SmartEvaluator/employees.db'
from wsgi import wsgi_app as application
```

Web 탭에서 Reload한다. 점검 표시가 유지된 상태에서 읽기 조회, 기존 완료 평가의 PDF·Excel 및 보존 건수를 확인한다. 오류가 있으면 Web 탭의 error log를 확인하고 점검 상태를 유지한다. 검증 후 `manage_db.py resume`으로 쓰기를 재개하고 로그인·신규 입력을 확인한다. 이전 버전으로 복구할 때는 코드와 DB를 함께 복구하며, 재개 후 새 제출이 생겼다면 이전 백업으로 바로 덮어쓰지 않는다.

공식 참고:

- [Flask 및 WSGI 설정](https://help.pythonanywhere.com/pages/Flask/)
- [가상환경 연결](https://help.pythonanywhere.com/pages/VirtualEnvForWebsites/)
- [WSGI에서 환경변수 설정](https://help.pythonanywhere.com/pages/environment-variables-for-web-apps/)
- [Reload 동작](https://help.pythonanywhere.com/pages/ReloadWebApp/)
