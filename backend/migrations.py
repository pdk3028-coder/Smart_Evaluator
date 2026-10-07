"""Explicit, backed-up SQLite upgrades. Never run upgrades on web-app import."""
import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
CORE_TABLES = ('employees', 'evaluation_projects', 'evaluation_assignments',
               'evaluations', 'evaluation_answers', 'evaluation_questions', 'system_settings', 'evaluation_types')

BASE_SCHEMA = {
    'employees': """id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        emp_id TEXT NOT NULL UNIQUE, ssn TEXT DEFAULT '', address_main TEXT,
        address_main_detail TEXT, phone TEXT, emergency_contact TEXT, gift_address TEXT,
        gift_address_detail TEXT, gift_receiver TEXT, privacy_agreed INTEGER DEFAULT 0,
        privacy_agreed_at TIMESTAMP, zipcode TEXT, gift_zipcode TEXT, last_updated TIMESTAMP,
        team_name TEXT, position TEXT""",
    'system_settings': 'key TEXT PRIMARY KEY, value TEXT NOT NULL',
    'evaluation_types': 'id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    'evaluation_rounds': 'id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    'evaluation_questions': """id INTEGER PRIMARY KEY AUTOINCREMENT, question_text TEXT NOT NULL,
        question_sub_text TEXT DEFAULT '', category TEXT NOT NULL, is_essay INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1,
        evaluation_type TEXT DEFAULT '동료사원 평가', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP""",
    'evaluation_projects': """id INTEGER PRIMARY KEY AUTOINCREMENT, evaluatee_id INTEGER NOT NULL,
        title TEXT NOT NULL, status TEXT DEFAULT 'active', start_date TEXT, end_date TEXT,
        evaluation_type TEXT DEFAULT '동료사원 평가', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        round_id INTEGER NOT NULL REFERENCES evaluation_rounds(id),
        FOREIGN KEY(evaluatee_id) REFERENCES employees(id) ON DELETE CASCADE,
        UNIQUE(round_id, evaluatee_id, evaluation_type)""",
    'evaluation_assignments': """id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
        evaluator_id INTEGER NOT NULL, status TEXT DEFAULT 'pending', assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES evaluation_projects(id) ON DELETE CASCADE,
        FOREIGN KEY(evaluator_id) REFERENCES employees(id) ON DELETE CASCADE, UNIQUE(project_id,evaluator_id)""",
    'evaluations': """id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER NOT NULL UNIQUE,
        evaluator_id INTEGER NOT NULL, evaluatee_id INTEGER NOT NULL, signature_data TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, finalized_at TEXT, record_snapshot TEXT,
        FOREIGN KEY(assignment_id) REFERENCES evaluation_assignments(id) ON DELETE CASCADE,
        FOREIGN KEY(evaluator_id) REFERENCES employees(id), FOREIGN KEY(evaluatee_id) REFERENCES employees(id)""",
    'evaluation_answers': """id INTEGER PRIMARY KEY AUTOINCREMENT, evaluation_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL, score INTEGER, answer_text TEXT,
        FOREIGN KEY(evaluation_id) REFERENCES evaluations(id) ON DELETE CASCADE,
        FOREIGN KEY(question_id) REFERENCES evaluation_questions(id)""",
    'project_question_snapshots': """project_id INTEGER NOT NULL REFERENCES evaluation_projects(id) ON DELETE CASCADE,
        question_id INTEGER NOT NULL REFERENCES evaluation_questions(id), question_text TEXT NOT NULL,
        question_sub_text TEXT, category TEXT NOT NULL, is_essay INTEGER NOT NULL, sort_order INTEGER,
        min_score INTEGER, max_score INTEGER, PRIMARY KEY(project_id,question_id)""",
    'schema_migrations': 'version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL',
}


def columns(conn, table):
    return [r['name'] for r in conn.execute(f'PRAGMA table_info("{table}")')]


def table_sql(conn, table):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row['sql'] if row else None


def add_column(conn, table, definition):
    if definition.split()[0] not in columns(conn, table):
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition}')


def split_definitions(sql):
    """Split CREATE clauses without splitting UNIQUE/FK argument lists."""
    body = sql[sql.index('(') + 1:sql.rindex(')')]
    result, start, depth, quote = [], 0, 0, None
    for i, char in enumerate(body):
        if quote:
            if char == quote:
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(body[start:i].strip())
            start = i + 1
    result.append(body[start:].strip())
    return result


def rebuild(conn, table, definitions):
    """Foreign keys must already be OFF, outside the active transaction.

    Preserve all existing columns, IDs, custom indexes/triggers and AUTOINCREMENT
    high-water marks. Do not rename the old table (SQLite rewrites child FKs).
    """
    old_columns = columns(conn, table)
    seq = conn.execute('SELECT seq FROM sqlite_sequence WHERE name=?', (table,)).fetchone() if table_sql(conn, 'sqlite_sequence') else None
    objects = conn.execute("SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL", (table,)).fetchall()
    temp = table + '_upgrade'
    conn.execute(f'CREATE TABLE "{temp}" ({", ".join(definitions)})')
    names = ','.join('"' + c + '"' for c in old_columns)
    conn.execute(f'INSERT INTO "{temp}" ({names}) SELECT {names} FROM "{table}"')
    conn.execute(f'DROP TABLE "{table}"')
    conn.execute(f'ALTER TABLE "{temp}" RENAME TO "{table}"')
    for obj in objects:
        sql = obj['sql']
        if table == 'evaluation_projects' and re.search(r'CREATE\s+UNIQUE\s+INDEX', sql, re.I):
            # Explicit indexes can enforce the old one-project-per-person rule, too.
            fields = re.search(r'\(([^)]+)\)', sql)
            if fields and {x.strip(' \t\n"`[]').lower() for x in fields[1].split(',')} in (
                    {'evaluatee_id'}, {'evaluatee_id', 'evaluation_type'}):
                sql = sql[:fields.start()] + '(round_id,evaluatee_id,evaluation_type)' + sql[fields.end():]
        conn.execute(sql)
    if seq:
        conn.execute('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?', (seq[0], table))


def fingerprints(conn):
    """Digest original columns only; later additive columns cannot hide losses."""
    result = {}
    for table in CORE_TABLES:
        cols = columns(conn, table)
        if not cols:
            continue
        rows = [list(r) for r in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
        result[table] = {'columns': cols, 'count': len(rows), 'digest': digest(rows)}
    return result


def digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


def verify_preserved(conn, before):
    for table, info in before.items():
        names = ','.join('"' + c + '"' for c in info['columns'])
        rows = [list(r) for r in conn.execute(f'SELECT {names} FROM "{table}" ORDER BY rowid')]
        if len(rows) != info['count'] or digest(rows) != info['digest']:
            raise RuntimeError(f'기존 자료 대조 실패: {table}. 변경을 취소합니다.')


def backup_database(db_path, backup_dir=None):
    path = Path(db_path).resolve()
    directory = Path(backup_dir).resolve() if backup_dir else path.parent / 'db_backups'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{path.stem}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.sqlite3'
    source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    dest = sqlite3.connect(str(target))
    try:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('백업 DB 무결성 검사 실패')
    finally:
        dest.close()
        source.close()
    os.chmod(target, 0o600)
    return str(target)


def migrate(db_path, backup_dir=None):
    """Run only during a write-stopped maintenance window; rollback on any mismatch."""
    existing = os.path.exists(db_path) and os.path.getsize(db_path) > 0
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    backup = None
    try:
        if table_sql(conn, 'schema_migrations'):
            version = conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
            if version == SCHEMA_VERSION:
                return {'changed': False, 'backup': None, 'version': version}
            if version and version > SCHEMA_VERSION:
                raise RuntimeError('더 새로운 DB 버전입니다. 이전 코드로 실행할 수 없습니다.')
        if existing:
            backup = backup_database(db_path, backup_dir)
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute('BEGIN EXCLUSIVE')
        before = fingerprints(conn)
        if backup:
            backup_conn = sqlite3.connect(Path(backup).as_uri() + '?mode=ro', uri=True)
            backup_conn.row_factory = sqlite3.Row
            try:
                if fingerprints(backup_conn) != before:
                    raise RuntimeError('백업 후 자료가 변경되었습니다. 모든 쓰기를 중지한 후 다시 실행하세요.')
            finally:
                backup_conn.close()
        for table in ('employees', 'system_settings', 'evaluation_types', 'evaluation_rounds', 'evaluation_questions'):
            conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ({BASE_SCHEMA[table]})')
        for field in ('team_name TEXT', 'position TEXT', 'phone TEXT', 'ssn TEXT DEFAULT \'\'',
                      'last_updated TIMESTAMP', 'privacy_agreed INTEGER DEFAULT 0', 'privacy_agreed_at TIMESTAMP'):
            add_column(conn, 'employees', field)
        for field in ("question_sub_text TEXT DEFAULT ''", 'sort_order INTEGER DEFAULT 0',
                      "evaluation_type TEXT DEFAULT '동료사원 평가'", 'is_active INTEGER DEFAULT 1'):
            add_column(conn, 'evaluation_questions', field)
        conn.execute("INSERT OR IGNORE INTO evaluation_rounds(name) VALUES ('기존 평가')")
        legacy_round = conn.execute("SELECT id FROM evaluation_rounds WHERE name='기존 평가'").fetchone()[0]
        if table_sql(conn, 'evaluation_projects'):
            for field in ('start_date TEXT', 'end_date TEXT', "evaluation_type TEXT DEFAULT '동료사원 평가'",
                          "status TEXT DEFAULT 'active'", 'created_at TIMESTAMP'):
                add_column(conn, 'evaluation_projects', field)
            add_column(conn, 'evaluation_projects', f'round_id INTEGER NOT NULL DEFAULT {legacy_round} REFERENCES evaluation_rounds(id)')
            definitions = []
            for clause in split_definitions(table_sql(conn, 'evaluation_projects')):
                unique = re.search(r'\bUNIQUE\s*\(([^)]+)\)', clause, re.I)
                if unique:
                    fields = {x.strip(' \t\n"`[]').lower() for x in unique[1].split(',')}
                    if fields in ({'evaluatee_id'}, {'evaluatee_id', 'evaluation_type'}):
                        continue
                if re.match(r'["`\[]?evaluatee_id\b', clause, re.I):
                    clause = re.sub(r'\bUNIQUE\b', '', clause, flags=re.I)
                definitions.append(clause)
            definitions.append('UNIQUE(round_id,evaluatee_id,evaluation_type)')
            rebuild(conn, 'evaluation_projects', definitions)
        else:
            conn.execute(f'CREATE TABLE evaluation_projects ({BASE_SCHEMA["evaluation_projects"]})')
        if table_sql(conn, 'evaluation_assignments') and 'project_id' not in columns(conn, 'evaluation_assignments'):
            add_column(conn, 'evaluation_assignments', 'project_id INTEGER REFERENCES evaluation_projects(id) ON DELETE CASCADE')
            for row in conn.execute('SELECT DISTINCT evaluatee_id FROM evaluation_assignments').fetchall():
                employee = conn.execute('SELECT name FROM employees WHERE id=?', (row[0],)).fetchone()
                if not employee:
                    raise RuntimeError('구형 배정에 존재하지 않는 사원이 있습니다. 원본을 확인하세요.')
                project = conn.execute("SELECT id FROM evaluation_projects WHERE evaluatee_id=? AND evaluation_type='동료사원 평가' AND round_id=?", (row[0], legacy_round)).fetchone()
                if not project:
                    project_id = conn.execute("INSERT INTO evaluation_projects(evaluatee_id,title,evaluation_type,round_id) VALUES (?,?,'동료사원 평가',?)", (row[0], employee[0] + ' 동료사원 평가', legacy_round)).lastrowid
                else:
                    project_id = project[0]
                conn.execute('UPDATE evaluation_assignments SET project_id=? WHERE evaluatee_id=?', (project_id, row[0]))
            definitions = []
            for clause in split_definitions(table_sql(conn, 'evaluation_assignments')):
                if re.match(r'["`\[]?evaluatee_id\b', clause, re.I):
                    clause = re.sub(r'\bNOT\s+NULL\b', '', clause, flags=re.I)
                definitions.append(clause)
            definitions.append('UNIQUE(project_id,evaluator_id)')
            rebuild(conn, 'evaluation_assignments', definitions)
        else:
            conn.execute(f'CREATE TABLE IF NOT EXISTS evaluation_assignments ({BASE_SCHEMA["evaluation_assignments"]})')
        conn.execute(f'CREATE TABLE IF NOT EXISTS evaluations ({BASE_SCHEMA["evaluations"]})')
        for field in ('signature_data TEXT', 'finalized_at TEXT', 'record_snapshot TEXT'):
            add_column(conn, 'evaluations', field)
        sql = table_sql(conn, 'evaluations')
        if 'evaluation_assignments_old' in sql:
            rebuild(conn, 'evaluations', split_definitions(sql.replace('evaluation_assignments_old', 'evaluation_assignments')))
        conn.execute(f'CREATE TABLE IF NOT EXISTS evaluation_answers ({BASE_SCHEMA["evaluation_answers"]})')
        conn.execute(f'CREATE TABLE project_question_snapshots ({BASE_SCHEMA["project_question_snapshots"]})')
        # Preserve existing scores, passwords, titles and questions verbatim.
        if not existing:
            from werkzeug.security import generate_password_hash
            conn.execute("INSERT INTO system_settings(key,value) VALUES ('admin_password',?)", (generate_password_hash('admin1234'),))
            for i, (text, category, essay) in enumerate([
                ('협업: 동료와 적극적으로 협력하고, 팀의 성과 향상에 기여하였습니까?', '협업', 0),
                ('의사소통: 타인의 의견을 존중하고, 명확하고 효과적으로 소통하였습니까?', '의사소통', 0),
                ('직무역량: 자신의 직무 역할에 책임을 다하며, 전문성을 발휘하였습니까?', '직무역량', 0),
                ('종합의견: 해당 동료에 대한 강점, 개선점 또는 하고 싶은 이야기를 자유롭게 작성해 주세요.', '종합의견', 1)], 1):
                conn.execute('INSERT INTO evaluation_questions(question_text,category,is_essay,sort_order) VALUES (?,?,?,?)', (text, category, essay, i))
        if 'evaluation_types' not in before:
            for name in ('동료사원 평가', '직무능력 평가', '다면평가'):
                conn.execute('INSERT OR IGNORE INTO evaluation_types(name) VALUES (?)', (name,))
        from records import freeze_project_questions, capture_record
        for project in conn.execute('SELECT id FROM evaluation_projects').fetchall():
            freeze_project_questions(conn, project[0], legacy=True)
        for row in conn.execute("SELECT ev.id, ev.assignment_id, ev.submitted_at FROM evaluations ev JOIN evaluation_assignments a ON a.id=ev.assignment_id WHERE a.status='completed' OR (ev.signature_data IS NOT NULL AND ev.signature_data <> '')").fetchall():
            snapshot = capture_record(conn, row['assignment_id'], source='legacy', evaluation_id=row['id'])
            conn.execute('UPDATE evaluations SET record_snapshot=?, finalized_at=? WHERE id=?',
                         (json.dumps(snapshot, ensure_ascii=False), row['submitted_at'], row['id']))
        verify_preserved(conn, before)
        errors = [tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
        if errors:
            raise RuntimeError(f'외래키 검사 실패: {errors[:10]}. 원본 확인이 필요합니다.')
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('DB 무결성 검사 실패')
        conn.execute(f'CREATE TABLE schema_migrations ({BASE_SCHEMA["schema_migrations"]})')
        conn.execute('INSERT INTO schema_migrations VALUES (?,?)', (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return {'changed': True, 'backup': backup, 'version': SCHEMA_VERSION, 'preserved': before}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_ready(db_path):
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        migrate(db_path)
        return
    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        version = conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
        if version != SCHEMA_VERSION:
            raise RuntimeError('DB 버전이 일치하지 않습니다.')
    except (sqlite3.Error, RuntimeError) as exc:
        raise RuntimeError('운영 DB 자동 변경을 중단했습니다. 쓰기를 중지하고 python manage_db.py migrate --maintenance를 실행하세요.') from exc
    finally:
        conn.close()
