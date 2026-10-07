import sqlite3
import os
import pandas as pd
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

import platform
from records import validate_period, freeze_project_questions, export_results

if platform.system() == 'Windows':
    DB_PATH = r"C:\Users\user06065\Desktop\Code Test\employees.db"
else:
    # PythonAnywhere 등 Linux 환경 대응
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(base_dir, "employees.db")


DB_PATH = os.environ.get("SMART_EVALUATOR_DB", DB_PATH)

def get_position_title(position):
    """
    직급(position) 값을 규칙에 맞게 매핑하여 노출용 직급 명칭을 반환합니다.
    - 직급이 한글인 경우는 그냥 한글 직급 그대로 쓰되, '파견사원', '일반직 사원'은 '사원'으로 변환.
    - 직급이 영문+숫자 혼합인 경우에는 A1, G5는 사원, G4는 대리, G3는 과장, G2는 차장, G1은 부장으로 변환.
    - 그 외 영숫자 혼합 직급은 '사원'으로 폴백 처리.
    - 비어있거나 누락된 경우는 '사원'으로 반환.
    """
    if not position:
        return "사원"
    
    pos = position.strip()
    
    # 1. 영문+숫자 혼합 매핑 사전
    eng_num_map = {
        "A1": "사원",
        "G5": "사원",
        "G4": "대리",
        "G3": "과장",
        "G2": "차장",
        "G1": "부장"
    }
    
    pos_upper = pos.upper()
    if pos_upper in eng_num_map:
        return eng_num_map[pos_upper]
        
    # 영문+숫자 혼합 형태인지 판단 (예: G6, ABC1 등)
    import re
    if re.match(r'^[A-Z]+\d+$', pos_upper):
        return "사원"
        
    # 2. 한글 직급 예외 처리
    if pos in ["파견사원", "일반직 사원", "일반직사원"]:
        return "사원"
        
    return pos

def get_all_evaluation_types():
    """등록된 모든 평가 종류의 이름을 리스트로 반환합니다."""
    conn = get_db_connection()
    rows = conn.execute('SELECT name FROM evaluation_types ORDER BY id ASC').fetchall()
    conn.close()
    return [row['name'] for row in rows]

def add_evaluation_type(name):
    """신규 평가 종류를 추가합니다."""
    if not name or not name.strip():
        raise Exception("평가 종류 이름이 올바르지 않습니다.")
    
    name = name.strip()
    conn = get_db_connection()
    c = conn.cursor()
    
    # 중복 체크
    exists = c.execute('SELECT id FROM evaluation_types WHERE name = ?', (name,)).fetchone()
    if exists:
        conn.close()
        raise Exception("이미 존재하는 평가 종류입니다.")
        
    c.execute('INSERT INTO evaluation_types (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()
    return True

def delete_evaluation_type(name):
    """평가 종류를 삭제합니다. 단, 해당 평가 종류를 사용 중인 프로젝트나 질문이 있으면 삭제할 수 없습니다."""
    if not name:
        raise Exception("삭제할 평가 종류 이름이 필요합니다.")
        
    name = name.strip()
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. evaluation_projects 사용 여부 체크
    proj_exists = c.execute('SELECT id FROM evaluation_projects WHERE evaluation_type = ?', (name,)).fetchone()
    if proj_exists:
        conn.close()
        raise Exception("해당 평가 종류를 사용하는 기존 평가 프로젝트가 존재하므로 삭제할 수 없습니다.")
        
    # 2. evaluation_questions 사용 여부 체크
    q_exists = c.execute('SELECT id FROM evaluation_questions WHERE evaluation_type = ?', (name,)).fetchone()
    if q_exists:
        conn.close()
        raise Exception("해당 평가 종류를 사용하는 등록된 평가 문항이 존재하므로 삭제할 수 없습니다.")
        
    # 삭제 수행
    c.execute('DELETE FROM evaluation_types WHERE name = ?', (name,))
    conn.commit()
    conn.close()
    return True

def get_db_connection():
    """데이터베이스 커넥션을 생성하여 반환합니다."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Explicit upgrade entry point for CLI/tests; web startup uses ensure_ready."""
    from migrations import migrate
    return migrate(DB_PATH)

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
    rows = conn.execute('SELECT id, name, emp_id, team_name, position, phone FROM employees ORDER BY name ASC').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def parse_employees_from_excel(filepath):
    """
    엑셀 파일을 읽고 쓰기 없이 사원 변경 후보를 반환합니다.
    1-based index 기준 다음 컬럼들을 매핑합니다.
      - 5번째 컬럼 (Index 4): 부서명
      - 6번째 컬럼 (Index 5): 실명
      - 7번째 컬럼 (Index 6): 팀명
      - 12번째 컬럼 (Index 11): 사번 (emp_id)
      - 13번째 컬럼 (Index 12): 성명 (name)
      - 16번째 컬럼 (Index 15): 직급 (position)
    
    팀명이 공란일 때 한 칸 좌측의 실명, 실명도 공란일 때 한 칸 좌측의 부서를 팀명으로 폴백 처리합니다.
    병합 셀은 상위 소속의 경계를 고려해 행 단위로 상속합니다.
    """
    df = pd.read_excel(filepath, dtype=str)
    if len(df.columns) < 16:
        raise ValueError("사원명부에는 소속·사번·성명·직급 열이 필요합니다. 명부 양식을 확인해 주세요.")
    
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

    # 병합 셀 대응을 위해 행 단위로 조직명 전파를 수행합니다.
    depts_list = []
    reals_list = []
    teams_list = []
    
    curr_dept = ""
    curr_real = ""
    curr_team = ""
    
    def clean_val_single(x):
        s = str(x).strip()
        if s.lower() in ['nan', 'none', '', 'nat']:
            return ''
        if s.endswith('.0'):
            return s[:-2]
        return s

    for i in range(len(df)):
        dept_val = clean_val_single(df.iloc[i, 4])
        real_val = clean_val_single(df.iloc[i, 5])
        team_val = clean_val_single(df.iloc[i, 6])
        
        # 세 소속 정보 필드가 모두 비어있을 때만 이전 행의 값을 전파합니다 (병합 셀 상속).
        # 특정 상위 부서명이 명시되어 있으면 이전 전파 상태를 리셋하고 해당 값들로 초기화합니다.
        is_all_empty = (not dept_val and not real_val and not team_val)
        
        if not is_all_empty:
            if dept_val:
                curr_dept = dept_val
                curr_real = real_val
                curr_team = team_val
            else:
                if real_val:
                    curr_real = real_val
                    curr_team = team_val
                if team_val:
                    curr_team = team_val
                    
        depts_list.append(curr_dept)
        reals_list.append(curr_real)
        teams_list.append(curr_team)

    depts = pd.Series(depts_list)
    reals = pd.Series(reals_list)
    teams = pd.Series(teams_list)

    emp_ids = clean_series(get_col(11))
    names = clean_series(get_col(12))
    positions = clean_series(get_col(15))
    phones = clean_series(get_col(52)) # 53번째 컬럼 (Index 52)

    records = []
    seen = set()
    for i in range(len(df)):
        emp_id, name = emp_ids.iloc[i], names.iloc[i]
        if not emp_id or not name or emp_id.upper() == 'ADMIN':
            continue
        if emp_id in seen:
            raise ValueError("명부에 중복 사번이 있습니다. 중복 행을 정리한 후 다시 업로드해 주세요.")
        seen.add(emp_id)
        records.append({'emp_id': emp_id, 'name': name,
                        'team_name': teams.iloc[i] or reals.iloc[i] or depts.iloc[i],
                        'position': positions.iloc[i], 'phone': phones.iloc[i]})
    if not records:
        raise ValueError("등록할 사원이 없습니다. 명부의 사번·성명 열을 확인해 주세요.")
    return records


def employee_import_plan(conn, records):
    changes = []
    inserted = updated = skipped = 0
    for employee in records:
        existing = conn.execute('SELECT name,team_name,position,phone FROM employees WHERE emp_id=?', (employee['emp_id'],)).fetchone()
        new = dict(employee)
        if existing and not new['phone']:
            new['phone'] = existing['phone'] or ''
        old = {key: existing[key] or '' for key in ('name','team_name','position','phone')} if existing else None
        values = {key: new[key] for key in ('name','team_name','position','phone')}
        if old is None:
            inserted += 1
        elif old != values:
            updated += 1
        else:
            skipped += 1
        changes.append({'employee': new, 'before': old, 'changed': old != values})
    from records import question_revision
    return {'inserted': inserted, 'updated': updated, 'skipped': skipped,
            'changes': changes, 'preview_token': question_revision(changes)}


def preview_employees_from_excel(filepath):
    records = parse_employees_from_excel(filepath)
    conn = get_db_connection()
    try:
        return employee_import_plan(conn, records)
    finally:
        conn.close()


def upsert_employees_from_excel(filepath, preview_token=None):
    records = parse_employees_from_excel(filepath)
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        plan = employee_import_plan(conn, records)
        if preview_token is not None and preview_token != plan['preview_token']:
            raise ValueError("미리보기 이후 명부 또는 사원 정보가 변경되었습니다. 다시 미리보기를 확인해 주세요.")
        now = datetime.now()
        for change in plan['changes']:
            if not change['changed']:
                continue
            employee = change['employee']
            if change['before'] is None:
                conn.execute('INSERT INTO employees(emp_id,name,team_name,position,phone,ssn,last_updated) VALUES (?,?,?,?,?,?,?)',
                             (employee['emp_id'],employee['name'],employee['team_name'],employee['position'],employee['phone'],'',now))
            else:
                conn.execute('UPDATE employees SET name=?,team_name=?,position=?,phone=?,last_updated=? WHERE emp_id=?',
                             (employee['name'],employee['team_name'],employee['position'],employee['phone'],now,employee['emp_id']))
        conn.execute('INSERT OR REPLACE INTO system_settings(key,value) VALUES (?,?)',
                     ('last_upload_time', datetime.now().strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        return plan['inserted'], plan['updated'], plan['skipped']
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_evaluation_project(evaluatee_id, evaluation_type="동료사원 평가", start_date=None, end_date=None, round_id=None):
    """Create a separate project per round; never overwrite a previous period."""
    validate_period(start_date, end_date)
    if type(round_id) is not int or round_id < 1:
        raise ValueError("평가 회차를 선택해 주세요. 화면을 새로고침한 후 다시 시도해 주세요.")
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        emp = conn.execute('SELECT name,position FROM employees WHERE id=?', (evaluatee_id,)).fetchone()
        if not emp:
            raise ValueError("존재하지 않는 사원입니다.")
        round_row = conn.execute('SELECT name FROM evaluation_rounds WHERE id=?', (round_id,)).fetchone()
        if not round_row:
            raise ValueError("존재하지 않는 평가 회차입니다.")
        if not conn.execute('SELECT id FROM evaluation_types WHERE name=?', (evaluation_type,)).fetchone():
            raise ValueError("등록되지 않은 평가 종류입니다.")
        if not conn.execute('SELECT id FROM evaluation_questions WHERE evaluation_type=? AND is_active=1', (evaluation_type,)).fetchone():
            raise ValueError("이 평가 종류에 사용할 문항을 먼저 등록해 주세요.")
        if conn.execute('SELECT id FROM evaluation_projects WHERE round_id=? AND evaluatee_id=? AND evaluation_type=?', (round_id,evaluatee_id,evaluation_type)).fetchone():
            raise ValueError("해당 회차에 같은 대상자·평가 종류의 프로젝트가 이미 존재합니다. 새 회차를 선택해 주세요.")
        title = f"{emp['name']} {get_position_title(emp['position'])} {evaluation_type} ({round_row['name']})"
        project_id = conn.execute('INSERT INTO evaluation_projects(evaluatee_id,title,evaluation_type,start_date,end_date,round_id) VALUES (?,?,?,?,?,?)',
                                 (evaluatee_id,title,evaluation_type,start_date or None,end_date or None,round_id)).lastrowid
        freeze_project_questions(conn, project_id)
        conn.commit()
        return project_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

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
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute('SELECT ev.id FROM evaluations ev JOIN evaluation_assignments a ON a.id=ev.assignment_id WHERE a.project_id=? LIMIT 1', (project_id,)).fetchone():
            raise ValueError("평가 기록이 있는 프로젝트는 삭제할 수 없습니다. 기존 자료를 보존합니다.")
        conn.execute('DELETE FROM evaluation_projects WHERE id=?', (project_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
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
            p.round_id, r.name AS round_name,
            datetime(p.created_at, 'localtime') as created_at,
            e.id as evaluatee_id, 
            e.name as evaluatee_name, 
            e.emp_id as evaluatee_emp_id,
            e.team_name as evaluatee_team, 
            e.position as evaluatee_position
        FROM evaluation_projects p
        JOIN evaluation_rounds r ON r.id = p.round_id
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
        c.execute('SELECT id, phone FROM employees WHERE emp_id = ?', (emp_id,))
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
    conn = get_db_connection()
    try:
        conn.execute('BEGIN')
        return export_results(conn)
    finally:
        conn.close()

def update_employee_info(emp_id, name, team_name, position, phone=None):
    """현재 사원 정보를 수정하고 기존 평가의 제목·인적사항은 보존합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        conn.execute('BEGIN IMMEDIATE')
        # 1. 사원 존재 여부 확인
        c.execute('SELECT id, phone FROM employees WHERE emp_id = ?', (emp_id,))
        emp_row = c.fetchone()
        if not emp_row:
            return False, "존재하지 않는 사원입니다."
        
        employee_id = emp_row['id']
        if phone is None:
            phone = emp_row['phone']
        now = datetime.now()
        
        # 2. 사원 정보 업데이트
        c.execute('''
            UPDATE employees
            SET name = ?, team_name = ?, position = ?, phone = ?, last_updated = ?
            WHERE id = ?
        ''', (name, team_name, position, phone, now, employee_id))
        
        # Project titles and submitted identity snapshots are historical records.
        conn.commit()
        return True, "사원 정보가 수정되었습니다. 기존 평가 기록은 보존됩니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_all_employees():
    """모든 임직원 정보를 삭제합니다. ON DELETE CASCADE 제약 조건에 의해 연쇄적으로 평가 데이터도 초기화됩니다."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT id FROM evaluations LIMIT 1').fetchone():
            return False, '평가 기록이 존재하여 전체 초기화를 제한했습니다. 기존 자료를 보존합니다.'
        c.execute('DELETE FROM employees')
        # 업로드 일시 기록도 초기화
        c.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('last_upload_time', '')")
        conn.commit()
        return True, "모든 사원 정보 및 관련 평가 데이터가 성공적으로 초기화되었습니다."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def update_privacy_agreement(emp_id):
    """사원의 개인정보 수집 및 이용 동의 시각을 현재 시각으로 기록합니다."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        now = datetime.now()
        c.execute('''
            UPDATE employees
            SET privacy_agreed = 1, privacy_agreed_at = ?
            WHERE emp_id = ?
        ''', (now, emp_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    # 로컬에서 데이터베이스 테이블 생성 테스트 진행
    init_db()
