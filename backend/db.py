import sqlite3
import os
import pandas as pd
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

import platform

if platform.system() == 'Windows':
    DB_PATH = r"C:\Users\user06065\Desktop\Code Test\employees.db"
else:
    # PythonAnywhere 등 Linux 환경 대응
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(base_dir, "employees.db")


def get_db_connection():
    """데이터베이스 커넥션을 생성하여 반환합니다."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """데이터베이스 테이블 구조 생성 및 마이그레이션을 수행합니다."""
    conn = get_db_connection()
    c = conn.cursor()

    # 1. employees 테이블 생성 (기존에 없을 경우 대비)
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emp_id TEXT NOT NULL UNIQUE,
            ssn TEXT DEFAULT '',
            address_main TEXT,
            address_main_detail TEXT,
            phone TEXT,
            emergency_contact TEXT,
            gift_address TEXT,
            gift_address_detail TEXT,
            gift_receiver TEXT,
            privacy_agreed INTEGER DEFAULT 0,
            privacy_agreed_at TIMESTAMP,
            zipcode TEXT,
            gift_zipcode TEXT,
            last_updated TIMESTAMP
        )
    ''')

    # 2. employees 테이블 마이그레이션 (team_name, position 컬럼 추가)
    cursor = c.execute("PRAGMA table_info(employees)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'team_name' not in columns:
        print("마이그레이션: employees 테이블에 team_name 컬럼을 추가합니다.")
        c.execute("ALTER TABLE employees ADD COLUMN team_name TEXT")

    if 'position' not in columns:
        print("마이그레이션: employees 테이블에 position 컬럼을 추가합니다.")
        c.execute("ALTER TABLE employees ADD COLUMN position TEXT")

    # 3. system_settings 테이블 생성
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # 4. evaluation_questions 테이블 생성 (평가 문항)
    c.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            question_sub_text TEXT DEFAULT '',
            category TEXT NOT NULL,
            is_essay INTEGER DEFAULT 0,  -- 0: 객관식(5점 척도), 1: 주관식(서술형)
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            evaluation_type TEXT DEFAULT '동료사원 평가',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # evaluation_projects 복합 유니크 마이그레이션 사전 검사
    cursor = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evaluation_projects'")
    proj_table_exists = cursor.fetchone() is not None

    if proj_table_exists:
        sql_row = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='evaluation_projects'").fetchone()
        proj_sql = sql_row['sql'] if sql_row else ""
        
        # 기존 테이블 정의에 UNIQUE 제약이 존재하고 복합 유니크 제약이 설정되어 있지 않은 경우 마이그레이션 수행
        if 'UNIQUE' in proj_sql and 'evaluation_type' not in proj_sql:
            print("마이그레이션: evaluation_projects 테이블을 복합 유니크(evaluatee_id, evaluation_type) 구조로 변경합니다.")
            c.execute("PRAGMA foreign_keys = OFF")
            
            # 임시 테이블 생성
            c.execute('''
                CREATE TABLE evaluation_projects_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    evaluatee_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    start_date TEXT,
                    end_date TEXT,
                    evaluation_type TEXT DEFAULT '동료사원 평가',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (evaluatee_id) REFERENCES employees (id) ON DELETE CASCADE,
                    UNIQUE(evaluatee_id, evaluation_type)
                )
            ''')
            
            # 기존 데이터 복사 (start_date, end_date가 존재할 수도 있고 아닐 수도 있으므로 pragma 체크 결과를 기준으로 복사)
            cursor_temp = c.execute("PRAGMA table_info(evaluation_projects)")
            temp_columns = [row[1] for row in cursor_temp.fetchall()]
            
            select_cols = "id, evaluatee_id, title, status, created_at"
            target_cols = "id, evaluatee_id, title, status, created_at"
            
            if 'start_date' in temp_columns:
                select_cols += ", start_date"
                target_cols += ", start_date"
            if 'end_date' in temp_columns:
                select_cols += ", end_date"
                target_cols += ", end_date"
                
            c.execute(f'''
                INSERT INTO evaluation_projects_new ({target_cols}, evaluation_type)
                SELECT {select_cols}, '동료사원 평가'
                FROM evaluation_projects
            ''')
            
            c.execute("DROP TABLE evaluation_projects")
            c.execute("ALTER TABLE evaluation_projects_new RENAME TO evaluation_projects")
            c.execute("PRAGMA foreign_keys = ON")
            print("마이그레이션: evaluation_projects 복합 유니크 개편 완료.")

    # 5. evaluation_assignments 및 evaluation_projects 테이블 마이그레이션 및 생성
    cursor = c.execute("PRAGMA table_info(evaluation_assignments)")
    columns = [row[1] for row in cursor.fetchall()]

    if columns and 'evaluatee_id' in columns:
        print("마이그레이션: evaluation_assignments 테이블을 프로젝트 기반 구조로 변경합니다.")
        
        # 기존 배정 데이터를 임시로 가져옵니다.
        old_assignments = c.execute('''
            SELECT a.id, a.evaluator_id, a.evaluatee_id, a.status, a.assigned_at, e.name as evaluatee_name 
            FROM evaluation_assignments a
            JOIN employees e ON a.evaluatee_id = e.id
        ''').fetchall()
        
        # evaluation_projects 테이블 생성
        c.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluatee_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                start_date TEXT,
                end_date TEXT,
                evaluation_type TEXT DEFAULT '동료사원 평가',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (evaluatee_id) REFERENCES employees (id) ON DELETE CASCADE,
                UNIQUE(evaluatee_id, evaluation_type)
            )
        ''')
        
        # 각 피평가자별로 프로젝트를 생성합니다.
        project_map = {}
        for row in old_assignments:
            ee_id = row['evaluatee_id']
            ee_name = row['evaluatee_name']
            if ee_id not in project_map:
                exist_proj = c.execute('SELECT id FROM evaluation_projects WHERE evaluatee_id = ? AND evaluation_type = ?', (ee_id, '동료사원 평가')).fetchone()
                if exist_proj:
                    project_map[ee_id] = exist_proj[0]
                else:
                    title = f"{ee_name} 사원 동료평가"
                    c.execute("INSERT INTO evaluation_projects (evaluatee_id, title, evaluation_type) VALUES (?, ?, '동료사원 평가')", (ee_id, title))
                    project_map[ee_id] = c.lastrowid
        
        # 기존 assignments 테이블 이름을 임시 변경
        c.execute('ALTER TABLE evaluation_assignments RENAME TO evaluation_assignments_old')
        
        # 새 구조의 evaluation_assignments 테이블 생성
        c.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                evaluator_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES evaluation_projects (id) ON DELETE CASCADE,
                FOREIGN KEY (evaluator_id) REFERENCES employees (id) ON DELETE CASCADE,
                UNIQUE(project_id, evaluator_id)
            )
        ''')
        
        # 데이터 이전
        for row in old_assignments:
            old_id = row['id']
            evaluator_id = row['evaluator_id']
            ee_id = row['evaluatee_id']
            status = row['status']
            assigned_at = row['assigned_at']
            project_id = project_map.get(ee_id)
            
            if project_id:
                c.execute('''
                    INSERT INTO evaluation_assignments (id, project_id, evaluator_id, status, assigned_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (old_id, project_id, evaluator_id, status, assigned_at))
                
        c.execute('DROP TABLE evaluation_assignments_old')
        print("마이그레이션: evaluation_assignments 테이블 변경 완료.")
    else:
        # 최초 테이블 생성 혹은 이미 마이그레이션된 상태
        c.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluatee_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                start_date TEXT,
                end_date TEXT,
                evaluation_type TEXT DEFAULT '동료사원 평가',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (evaluatee_id) REFERENCES employees (id) ON DELETE CASCADE,
                UNIQUE(evaluatee_id, evaluation_type)
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS evaluation_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                evaluator_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES evaluation_projects (id) ON DELETE CASCADE,
                FOREIGN KEY (evaluator_id) REFERENCES employees (id) ON DELETE CASCADE,
                UNIQUE(project_id, evaluator_id)
            )
        ''')

    # evaluation_projects 테이블 컬럼 마이그레이션 (start_date, end_date, evaluation_type 추가)
    cursor = c.execute("PRAGMA table_info(evaluation_projects)")
    proj_columns = [row[1] for row in cursor.fetchall()]
    if 'start_date' not in proj_columns:
        print("마이그레이션: evaluation_projects 테이블에 start_date 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluation_projects ADD COLUMN start_date TEXT")
    if 'end_date' not in proj_columns:
        print("마이그레이션: evaluation_projects 테이블에 end_date 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluation_projects ADD COLUMN end_date TEXT")
    if 'evaluation_type' not in proj_columns:
        print("마이그레이션: evaluation_projects 테이블에 evaluation_type 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluation_projects ADD COLUMN evaluation_type TEXT DEFAULT '동료사원 평가'")

    # evaluation_questions 테이블 컬럼 마이그레이션 (sort_order, question_sub_text, evaluation_type 추가)
    cursor = c.execute("PRAGMA table_info(evaluation_questions)")
    q_columns = [row[1] for row in cursor.fetchall()]
    if 'sort_order' not in q_columns:
        print("마이그레이션: evaluation_questions 테이블에 sort_order 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluation_questions ADD COLUMN sort_order INTEGER DEFAULT 0")
        c.execute("UPDATE evaluation_questions SET sort_order = id")

    if 'question_sub_text' not in q_columns:
        print("마이그레이션: evaluation_questions 테이블에 question_sub_text 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluation_questions ADD COLUMN question_sub_text TEXT DEFAULT ''")

    if 'evaluation_type' not in q_columns:
        print("마이그레이션: evaluation_questions 테이블에 evaluation_type 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluation_questions ADD COLUMN evaluation_type TEXT DEFAULT '동료사원 평가'")

    # 6. evaluations 테이블 생성 및 마이그레이션 (평가 제출 기본 정보)
    eval_sql_row = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='evaluations'").fetchone()
    if eval_sql_row and 'evaluation_assignments_old' in eval_sql_row['sql']:
        print("마이그레이션: evaluations 테이블의 외래키 참조를 evaluation_assignments_old에서 evaluation_assignments로 정정합니다.")
        old_evaluations = c.execute("SELECT * FROM evaluations").fetchall()
        c.execute("DROP TABLE evaluations")
        c.execute('''
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL UNIQUE,
                evaluator_id INTEGER NOT NULL,
                evaluatee_id INTEGER NOT NULL,
                signature_data TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES evaluation_assignments (id) ON DELETE CASCADE,
                FOREIGN KEY (evaluator_id) REFERENCES employees (id),
                FOREIGN KEY (evaluatee_id) REFERENCES employees (id)
            )
        ''')
        for row in old_evaluations:
            row_dict = dict(row)
            sig_val = row_dict.get('signature_data', None)
            c.execute('''
                INSERT INTO evaluations (id, assignment_id, evaluator_id, evaluatee_id, signature_data, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (row_dict['id'], row_dict['assignment_id'], row_dict['evaluator_id'], row_dict['evaluatee_id'], sig_val, row_dict['submitted_at']))
        print("마이그레이션: evaluations 테이블 정정 완료.")
    else:
        c.execute('''
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL UNIQUE,
                evaluator_id INTEGER NOT NULL,
                evaluatee_id INTEGER NOT NULL,
                signature_data TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES evaluation_assignments (id) ON DELETE CASCADE,
                FOREIGN KEY (evaluator_id) REFERENCES employees (id),
                FOREIGN KEY (evaluatee_id) REFERENCES employees (id)
            )
        ''')

    # evaluations 테이블에 signature_data 컬럼 마이그레이션 (기존 테이블 존재 시 추가)
    cursor = c.execute("PRAGMA table_info(evaluations)")
    eval_columns = [row[1] for row in cursor.fetchall()]
    if 'signature_data' not in eval_columns:
        print("마이그레이션: evaluations 테이블에 signature_data 컬럼을 추가합니다.")
        c.execute("ALTER TABLE evaluations ADD COLUMN signature_data TEXT")

    # 7. evaluation_answers 테이블 생성 (각 문항별 답변 상세)
    c.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            score INTEGER,       -- 객관식 답변 (1~5점)
            answer_text TEXT,    -- 주관식 답변
            FOREIGN KEY (evaluation_id) REFERENCES evaluations (id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES evaluation_questions (id)
        )
    ''')

    # 관리자 패스워드 설정 (ADMIN 계정 비밀번호)
    pw_row = c.execute("SELECT value FROM system_settings WHERE key = 'admin_password'").fetchone()
    if not pw_row:
        default_hash = generate_password_hash('admin1234')
        c.execute("INSERT INTO system_settings (key, value) VALUES ('admin_password', ?)", (default_hash,))
        print("마이그레이션: 기본 관리자 비밀번호(admin1234)를 등록했습니다.")

    # 기본 평가 문항 자동 삽입
    cursor = c.execute("SELECT COUNT(*) FROM evaluation_questions")
    q_count = cursor.fetchone()[0]
    if q_count == 0:
        default_questions = [
            ("협업: 동료와 적극적으로 협력하고, 팀의 성과 향상에 기여하였습니까?", "협업", 0),
            ("의사소통: 타인의 의견을 존중하고, 명확하고 효과적으로 소통하였습니까?", "의사소통", 0),
            ("직무역량: 자신의 직무 역할에 책임을 다하며, 전문성을 발휘하였습니까?", "직무역량", 0),
            ("종합의견: 해당 동료에 대한 강점, 개선점 또는 하고 싶은 이야기를 자유롭게 작성해 주세요.", "종합의견", 1)
        ]
        for idx, (q_text, cat, is_essay) in enumerate(default_questions):
            c.execute('''
                INSERT INTO evaluation_questions (question_text, category, is_essay, sort_order, evaluation_type)
                VALUES (?, ?, ?, ?, '동료사원 평가')
            ''', (q_text, cat, is_essay, idx + 1))
        print("마이그레이션: 기본 평가 문항 4개를 등록했습니다.")

    # 기존 1~5점 척도 점수를 6~10점 척도로 일괄 업데이트
    c.execute("UPDATE evaluation_answers SET score = score + 5 WHERE score >= 1 AND score <= 5")
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def get_setting(key, default=''):
    """시스템 설정을 조회합니다."""
    conn = get_db_connection()
    row = conn.execute('SELECT value FROM system_settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    """시스템 설정을 저장하거나 업데이트합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def verify_admin_password(input_password):
    """입력된 관리자 비밀번호가 일치하는지 검증합니다."""
    stored_hash = get_setting('admin_password', '')
    if not stored_hash:
        return False
    return check_password_hash(stored_hash, input_password)

def set_admin_password(new_password):
    """관리자 비밀번호를 업데이트합니다."""
    hashed = generate_password_hash(new_password)
    set_setting('admin_password', hashed)

def get_employee_by_emp_id(emp_id):
    """사번으로 임직원 정보를 조회합니다."""
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM employees WHERE emp_id = ?', (emp_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_employees():
    """전체 사원 정보를 반환합니다."""
    conn = get_db_connection()
    rows = conn.execute('SELECT id, name, emp_id, team_name, position FROM employees ORDER BY name ASC').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def upsert_employees_from_excel(filepath):
    """
    엑셀 파일을 읽고 사원 데이터를 업데이트/삽입합니다.
    1-based index 기준 다음 컬럼들을 매핑합니다.
      - 5번째 컬럼 (Index 4): 부서명
      - 6번째 컬럼 (Index 5): 실명
      - 7번째 컬럼 (Index 6): 팀명
      - 12번째 컬럼 (Index 11): 사번 (emp_id)
      - 13번째 컬럼 (Index 12): 성명 (name)
      - 16번째 컬럼 (Index 15): 직급 (position)
    
    팀명이 공란일 때 한 칸 좌측의 실명, 실명도 공란일 때 한 칸 좌측의 부서를 팀명으로 폴백 처리합니다.
    엑셀 병합 셀에 대응하기 위해 각 소속 컬럼에 대해 ffill()을 먼저 수행합니다.
    """
    df = pd.read_excel(filepath, dtype=str)
    
    # 0-based index 기준 데이터 컬럼 안전 추출
    def get_col(col_idx):
        if col_idx < len(df.columns):
            return df.iloc[:, col_idx]
        return pd.Series([''] * len(df))

    # 데이터 정리 함수 (NaN 및 .0 제거)
    def clean_series(series):
        def clean_val(x):
            s = str(x).strip()
            if s.lower() in ['nan', 'none', '', 'nat']:
                return ''
            if s.endswith('.0'):
                return s[:-2]
            return s
        return series.apply(clean_val)

    # 병합 셀 대응을 위해 ffill() 수행 후 클렌징
    dept_raw = get_col(4).ffill()
    real_raw = get_col(5).ffill()
    team_raw = get_col(6).ffill()

    depts = clean_series(dept_raw)
    reals = clean_series(real_raw)
    teams = clean_series(team_raw)

    emp_ids = clean_series(get_col(11))
    names = clean_series(get_col(12))
    positions = clean_series(get_col(15))
    phones = clean_series(get_col(52)) # 53번째 컬럼 (Index 52)

    conn = get_db_connection()
    c = conn.cursor()
    
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    
    for i in range(len(df)):
        emp_id = emp_ids.iloc[i]
        name = names.iloc[i]
        position = positions.iloc[i]
        phone_val = phones.iloc[i]
        
        # 사번과 이름이 모두 유효해야 등록
        if not emp_id or not name:
            continue
            
        # 관리자 계정('ADMIN')은 엑셀 데이터로 덮어쓰지 않음
        if emp_id.upper() == 'ADMIN':
            continue

        # 팀명 -> 실명 -> 부서 순의 폴백 로직 적용
        dept_val = depts.iloc[i]
        real_val = reals.iloc[i]
        team_val = teams.iloc[i]
        
        final_team = team_val
        if not final_team:
            final_team = real_val
            if not final_team:
                final_team = dept_val

        # 사원 존재 여부 및 기존 정보 조회
        c.execute('SELECT name, team_name, position, phone FROM employees WHERE emp_id = ?', (emp_id,))
        existing = c.fetchone()
        
        now = datetime.now()
        if existing:
            # 기존 데이터와 엑셀 데이터 비교 (None/NaN 고려)
            existing_name = existing['name'] or ''
            existing_team = existing['team_name'] or ''
            existing_position = existing['position'] or ''
            existing_phone = existing['phone'] or ''
            
            is_changed = (
                existing_name != name or
                existing_team != final_team or
                existing_position != position or
                existing_phone != phone_val
            )
            
            if is_changed:
                c.execute('''
                    UPDATE employees
                    SET name = ?, team_name = ?, position = ?, phone = ?, last_updated = ?
                    WHERE emp_id = ?
                ''', (name, final_team, position, phone_val, now, emp_id))
                updated_count += 1
            else:
                skipped_count += 1
        else:
            c.execute('''
                INSERT INTO employees (name, emp_id, team_name, position, phone, ssn, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, emp_id, final_team, position, phone_val, '', now))
            inserted_count += 1
        
    # 최근 업로드 일시 기록
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)', ('last_upload_time', now_str))
    
    conn.commit()
    conn.close()
    return inserted_count, updated_count, skipped_count

def create_evaluation_project(evaluatee_id, evaluation_type="동료사원 평가", start_date=None, end_date=None):
    """피평가자 ID와 평가 종류로 평가 프로젝트를 생성합니다. 이미 존재하면 기존 프로젝트 ID를 반환하고 기간을 업데이트합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    
    emp = c.execute('SELECT name FROM employees WHERE id = ?', (evaluatee_id,)).fetchone()
    if not emp:
        conn.close()
        raise Exception("존재하지 않는 사원입니다.")
    
    title = f"{emp['name']} 사원 {evaluation_type}"
    
    existing = c.execute('''
        SELECT id FROM evaluation_projects 
        WHERE evaluatee_id = ? AND evaluation_type = ?
    ''', (evaluatee_id, evaluation_type)).fetchone()
    
    if existing:
        if start_date and end_date:
            c.execute('''
                UPDATE evaluation_projects
                SET start_date = ?, end_date = ?
                WHERE id = ?
            ''', (start_date, end_date, existing['id']))
            conn.commit()
        conn.close()
        return existing['id']
        
    c.execute('''
        INSERT INTO evaluation_projects (evaluatee_id, title, evaluation_type, start_date, end_date)
        VALUES (?, ?, ?, ?, ?)
    ''', (evaluatee_id, title, evaluation_type, start_date, end_date))
    project_id = c.lastrowid
    conn.commit()
    conn.close()
    return project_id

def add_evaluator_to_project(project_id, evaluator_id):
    """프로젝트에 평가자를 배정합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 중복 체크
    exists = c.execute('''
        SELECT id FROM evaluation_assignments 
        WHERE project_id = ? AND evaluator_id = ?
    ''', (project_id, evaluator_id)).fetchone()
    
    if exists:
        conn.close()
        raise Exception("이미 배정된 평가자입니다.")
        
    c.execute('''
        INSERT INTO evaluation_assignments (project_id, evaluator_id)
        VALUES (?, ?)
    ''', (project_id, evaluator_id))
    conn.commit()
    conn.close()

def delete_evaluation_project(project_id):
    """평가 프로젝트를 삭제합니다. ON DELETE CASCADE에 의해 배정 정보도 연쇄 삭제됩니다."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM evaluation_projects WHERE id = ?', (project_id,))
    conn.commit()
    conn.close()

def get_all_projects():
    """모든 평가 프로젝트와 피평가자 정보를 가져옵니다."""
    conn = get_db_connection()
    query = '''
        SELECT 
            p.id as project_id, 
            p.title, 
            p.status, 
            p.start_date,
            p.end_date,
            p.evaluation_type,
            datetime(p.created_at, 'localtime') as created_at,
            e.id as evaluatee_id, 
            e.name as evaluatee_name, 
            e.emp_id as evaluatee_emp_id,
            e.team_name as evaluatee_team, 
            e.position as evaluatee_position
        FROM evaluation_projects p
        JOIN employees e ON p.evaluatee_id = e.id
        ORDER BY p.created_at DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def insert_single_employee(emp_id, name, team_name="", position="", phone=""):
    """개별 사원을 직접 등록합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # 사번 중복 검사
        c.execute('SELECT id FROM employees WHERE emp_id = ?', (emp_id,))
        if c.fetchone():
            return False, "이미 등록된 사번입니다."

        now = datetime.now()
        c.execute('''
            INSERT INTO employees (emp_id, name, team_name, position, phone, ssn, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, name, team_name, position, phone, '', now))
        conn.commit()
        return True, "사원이 성공적으로 등록되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_evaluation_results_for_export():
    """엑셀 다운로드용 전체 평가 결과를 조회하고 피벗하여 정리합니다."""
    conn = get_db_connection()
    query = '''
        SELECT 
            p.title AS project_title,
            ee.emp_id AS evaluatee_emp_id,
            ee.name AS evaluatee_name,
            ee.team_name AS evaluatee_team,
            ee.position AS evaluatee_position,
            er.emp_id AS evaluator_emp_id,
            er.name AS evaluator_name,
            er.team_name AS evaluator_team,
            er.position AS evaluator_position,
            a.status AS assignment_status,
            datetime(ev.submitted_at, 'localtime') AS submitted_at,
            q.question_text AS question_text,
            ans.score AS score,
            ans.answer_text AS answer_text,
            q.is_essay AS is_essay
        FROM evaluation_assignments a
        JOIN evaluation_projects p ON a.project_id = p.id
        JOIN employees ee ON p.evaluatee_id = ee.id
        JOIN employees er ON a.evaluator_id = er.id
        LEFT JOIN evaluations ev ON ev.assignment_id = a.id
        LEFT JOIN evaluation_answers ans ON ans.evaluation_id = ev.id
        LEFT JOIN evaluation_questions q ON ans.question_id = q.id
        ORDER BY p.id, ee.id, er.id, q.sort_order
    '''
    df = pd.read_sql_query(query, conn)
    
    # 평가문항 순서(sort_order)대로 컬럼 재배치용 질문 리스트 조회
    q_rows = conn.execute('SELECT question_text FROM evaluation_questions WHERE is_active = 1 ORDER BY sort_order ASC').fetchall()
    question_order = [r['question_text'] for r in q_rows]
    
    # 객관식 질문 리스트 조회 (총점 계산용)
    obj_q_rows = conn.execute('SELECT question_text FROM evaluation_questions WHERE is_active = 1 AND is_essay = 0').fetchall()
    obj_questions = [r['question_text'] for r in obj_q_rows]
    
    conn.close()
    
    if df.empty:
        return df

    # 배정 상태 명칭 한글 매핑
    status_map = {'pending': '대기', 'saved': '임시 저장', 'completed': '완료'}
    df['assignment_status'] = df['assignment_status'].map(status_map).fillna(df['assignment_status'])

    # 개별 답변 값 가공 (객관식은 점수, 주관식은 텍스트)
    df['val'] = df.apply(
        lambda r: r['answer_text'] if r['is_essay'] == 1 else (str(int(float(r['score']))) if pd.notnull(r['score']) else ''),
        axis=1
    )
    
    # 배정 기본 키 정보 리스트
    index_cols = [
        'project_title', 'evaluatee_emp_id', 'evaluatee_name', 'evaluatee_team', 'evaluatee_position',
        'evaluator_emp_id', 'evaluator_name', 'evaluator_team', 'evaluator_position',
        'assignment_status', 'submitted_at'
    ]
    
    # 피벗 테이블 생성
    pivot_df = df.pivot_table(
        index=index_cols,
        columns='question_text',
        values='val',
        aggfunc='first'
    ).reset_index()
    
    # 평가 총점 계산 (객관식 점수 합산)
    def calculate_total_score(row):
        total = 0
        has_any = False
        for q_txt in obj_questions:
            if q_txt in row and pd.notnull(row[q_txt]) and str(row[q_txt]).strip() != '':
                try:
                    total += int(float(str(row[q_txt])))
                    has_any = True
                except ValueError:
                    pass
        return total if has_any else ''
        
    pivot_df['평가 총점'] = pivot_df.apply(calculate_total_score, axis=1)
    
    # 컬럼 순서 재배치: 기본 정보 + 문항 정렬 순서 + 평가 총점
    existing_questions = [q_col for q_col in question_order if q_col in pivot_df.columns]
    ordered_cols = index_cols + existing_questions + ['평가 총점']
    
    # 실제 존재하는 컬럼 필터링
    ordered_cols = [c for c in ordered_cols if c in pivot_df.columns]
    pivot_df = pivot_df[ordered_cols]
    
    # 컬럼명 한글로 매핑
    pivot_df.rename(columns={
        'project_title': '프로젝트명',
        'evaluatee_emp_id': '피평가자 사번',
        'evaluatee_name': '피평가자 성명',
        'evaluatee_team': '피평가자 부서',
        'evaluatee_position': '피평가자 직급',
        'evaluator_emp_id': '평가자 사번',
        'evaluator_name': '평가자 성명',
        'evaluator_team': '평가자 부서',
        'evaluator_position': '평가자 직급',
        'assignment_status': '배정 상태',
        'submitted_at': '제출 일시'
    }, inplace=True)
    
    return pivot_df

if __name__ == '__main__':
    # 로컬에서 데이터베이스 테이블 생성 테스트 진행
    init_db()
