"""Read-only inspection, copy rehearsals, and explicit maintenance upgrades."""
import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path

from migrations import backup_database, fingerprints, migrate


def main():
    parser = argparse.ArgumentParser(description='자료 보존 DB 관리. 운영 이전 전에 dry-run을 실행하세요.')
    parser.add_argument('command', choices=['inspect', 'backup', 'dry-run', 'migrate', 'pause', 'resume'])
    parser.add_argument('--db', required=True, help='대상 DB의 명시적인 경로')
    parser.add_argument('--backup-dir')
    parser.add_argument('--maintenance', action='store_true', help='모든 기존 서버의 쓰기를 중지했음을 확인')
    args = parser.parse_args()
    path = Path(args.db).resolve()
    if not path.is_file():
        parser.error('DB 파일을 찾을 수 없습니다. 새 운영 DB를 자동 생성하지 않습니다.')
    marker = str(path) + '.maintenance'
    if args.command == 'pause':
        Path(marker).touch()
        print('점검 표시를 설정했습니다. 구버전 서버는 별도로 중지해야 합니다.')
    elif args.command == 'resume':
        if os.path.exists(marker):
            os.remove(marker)
        print('점검 표시를 해제했습니다.')
    elif args.command == 'backup':
        print(json.dumps({'backup': backup_database(path, args.backup_dir)}, ensure_ascii=False))
    elif args.command == 'migrate':
        if not args.maintenance:
            parser.error('모든 쓰기 요청을 중지한 후 --maintenance를 지정하세요.')
        Path(marker).touch()
        print(json.dumps(migrate(str(path), args.backup_dir), ensure_ascii=False, indent=2))
        print('점검 표시는 유지됩니다. 검증 후 resume으로 해제하세요.')
    else:
        conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        try:
            if args.command == 'inspect':
                print(json.dumps({'tables': fingerprints(conn),
                    'integrity': conn.execute('PRAGMA integrity_check').fetchone()[0],
                    'foreign_key_violations': len(conn.execute('PRAGMA foreign_key_check').fetchall())},
                    ensure_ascii=False, indent=2))
            else:
                with tempfile.TemporaryDirectory(prefix='evaluator-rehearsal-') as directory:
                    clone = str(Path(directory) / 'rehearsal.db')
                    dest = sqlite3.connect(clone)
                    try:
                        conn.backup(dest)
                    finally:
                        dest.close()
                    result = migrate(clone)
                    result['backup'] = '(복제본의 임시 백업)'
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    print('원본 DB는 읽기 전용으로 사용했습니다.')
        finally:
            conn.close()


if __name__ == '__main__':
    main()
