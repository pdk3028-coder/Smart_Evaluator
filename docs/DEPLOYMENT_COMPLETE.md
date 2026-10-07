# PythonAnywhere 운영 적용 기록

2026-10-07, 사용자의 운영 적용 요청에 따라 `SmartEvaluator` 계정의 서비스를 업데이트하고 재개했다.

- 서비스: <https://smartevaluator.pythonanywhere.com/>
- 배포한 기능 코드: [8903766](https://github.com/pdk3028-coder/Smart_Evaluator/commit/8903766c5b47df5071d30dacea4a38ca3901e703)
- GitHub `master`에 기능 개선 커밋 반영
- 운영 코드: `/home/SmartEvaluator/backend`
- 운영 DB: `/home/SmartEvaluator/employees.db`
- 가상환경: `/home/SmartEvaluator/.virtualenvs/myenv`, Python 3.10
- WSGI: `/var/www/smartevaluator_pythonanywhere_com_wsgi.py`
- WSGI에서 앱 import 전에 운영 DB 절대경로를 명시했다.
- 로그인·인증 로직은 기존 코드를 유지했다.

## 보존 확인

| 대상 | 이전 전·후 건수 |
| --- | ---: |
| 사원 | 1,027 |
| 프로젝트 | 30 |
| 평가 배정 | 345 |
| 평가 | 249 |
| 평가 답변 | 2,739 |
| 평가 문항 | 11 |
| 평가 유형 | 3 |
| 시스템 설정 | 2 |

이전 트랜잭션 안에서 기존 열의 모든 값·ID·건수·해시를 대조했다. 코드 반영 후, 웹 앱 재시작 후에도 읽기 전용 대조를 다시 통과했다. 외래키 및 DB 무결성 검사를 통과했다. 새 문항·회차·기록 고정 정보를 위한 열과 테이블은 추가됐으므로 DB 파일 자체의 바이트 해시는 이전 전과 같지 않다.

## 백업과 점검 순서

운영 백업 디렉터리:

`/home/SmartEvaluator/deploy_backup_20261007_8903766`

주요 보관 파일:

- `code-before.tar`: 이전 코드·정적 파일·프런트엔드 소스
- `wsgi-before.py`: 이전 WSGI 설정
- `employees-20261007T120400174896Z.sqlite3`: 서비스 중단 전 SQLite 백업
- `employees-20261007T120714241694Z.sqlite3`: 쓰기 중단 후 실제 이전 직전 SQLite 백업
- `tests.log`, `rehearsal.json`, `migration.log`, `after.json`, `health.json`: 검증 결과
- `results-after.xlsx`: 실제 운영 Excel 출력 대조용 파일

백업은 공개 정적 경로 밖에 보관했고, 디렉터리를 700으로 생성했다. DB 백업 파일 권한은 600으로 설정했다. 배포 백업과 준비 디렉터리는 `.gitignore`에서 제외했다. DB·명부·백업·운영 Excel은 GitHub에 업로드하지 않았다.

현재 코드·DB 백업 → 분리된 배포 코드로 운영 가상환경 테스트 → 최신 DB 읽기 전용 복제본 이전 → DB를 import하지 않는 임시 WSGI 점검 응답으로 Reload → 실제 API 503 확인 → 이전 직전 DB 재백업 및 운영 이전 → GitHub 개선 코드 반영 → 새 앱 조회·Excel 시험 → 새 WSGI로 Reload → 원본 값 재대조 → 점검 표시 해제 순서로 진행했다. 별도 예약·상시 작업이 없고 실행 작업 목록도 비어 있음을 확인했다.

## 실제 확인 결과

- 운영 가상환경에서 백업 복제 검증을 포함한 **23개 테스트 통과**
- 운영 DB의 읽기 전용 복제본 이전 성공
- 실제 조회 API HTTP 200, 사원 수 1,027 확인
- 점검 중 실제 제출 API HTTP 503
- 재개 후 구버전 화면 제출 HTTP 409
- 재개 후 빈 제출 데이터 HTTP 400
- 실제 운영 Excel 다운로드 HTTP 200, **배정 전체 345행** 확인
- Excel의 **기존 평가 249건 각각의 총점이 이전 직전 백업과 동일**함을 확인
- 로그인 화면과 최신 프런트엔드 번들 `index-B97IIgTH.js` 정상 표시
- 로그인 빈 입력 검증 HTTP 400

신규 평가 저장·최종 제출, 기록 고정, 동시 제출 차단과 PDF HTML 삽입 방어는 가상 DB 테스트 및 가상 평가 화면에서 검증했다. 운영 검증은 기존 자료의 조회·Excel 대조와 자료를 생성하지 않는 오류 요청으로 수행했다.

복구가 필요하면 먼저 쓰기를 중단하고 현재 DB를 추가 백업한다. 서비스 재개 후의 새 제출을 보존해야 하므로 이전 직전 백업으로 바로 덮어쓰지 않는다. 세부 절차는 [적용·복구 안내](DEPLOYMENT.md)를 따른다.
