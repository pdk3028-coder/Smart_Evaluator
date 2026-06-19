from flask import Blueprint, request, jsonify, send_file
import os
import shutil
import io
import db
import pandas as pd
import sqlite3
import datetime
import platform

api_bp = Blueprint('api', __name__)

@api_bp.route("/auth/login", methods=["POST"])
def login():
    """사원번호(사번) 로그인 및 관리자 패스워드 인증을 진행합니다."""
    data = request.get_json() or {}
    emp_id = data.get("emp_id")
    password = data.get("password")

    if not emp_id:
        return jsonify({"detail": "사원번호를 입력해주세요."}), 400
        
    emp_id = emp_id.strip()
    if not emp_id:
        return jsonify({"detail": "사원번호를 입력해주세요."}), 400
        
    # 관리자 로그인 처리
    if emp_id.upper() == 'ADMIN':
        if not password:
            return jsonify({"detail": "관리자 비밀번호를 입력해주세요."}), 400
        if db.verify_admin_password(password):
            return jsonify({
                "success": True,
                "is_admin": True,
                "emp_id": "ADMIN",
                "emp_name": "관리자",
                "token": "admin-session-token-placeholder"
            })
        else:
            return jsonify({"detail": "비밀번호가 올바르지 않습니다."}), 401
            
    # 일반 임직원 로그인 처리
    user = db.get_employee_by_emp_id(emp_id)
    if user:
        return jsonify({
            "success": True,
            "is_admin": False,
            "id": user["id"],
            "emp_id": user["emp_id"],
            "emp_name": user["name"],
            "token": f"user-session-token-{user['id']}"
        })
    else:
        return jsonify({"detail": "등록되지 않은 사번입니다."}), 404

@api_bp.route("/evaluation-types", methods=["GET"])
def get_evaluation_types():
    """모든 평가 종류 목록을 반환합니다."""
    try:
        types = db.get_all_evaluation_types()
        return jsonify(types)
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@api_bp.route("/admin/evaluation-types", methods=["POST"])
def create_evaluation_type():
    """새로운 평가 종류를 추가합니다."""
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"detail": "평가 종류 이름이 필요합니다."}), 400
    try:
        db.add_evaluation_type(name)
        return jsonify({"success": True, "message": "평가 종류가 추가되었습니다."})
    except Exception as e:
        return jsonify({"detail": str(e)}), 400

@api_bp.route("/admin/evaluation-types", methods=["DELETE"])
def delete_evaluation_type_api():
    """평가 종류를 삭제합니다."""
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"detail": "삭제할 평가 종류 이름이 필요합니다."}), 400
    try:
        db.delete_evaluation_type(name)
        return jsonify({"success": True, "message": "평가 종류가 삭제되었습니다."})
    except Exception as e:
        return jsonify({"detail": str(e)}), 400

@api_bp.route("/evaluations/assignments", methods=["GET"])
def get_assignments():
    """로그인한 평가자에게 지정된 평가 프로젝트(피평가자) 목록을 반환합니다. 평가 기간에 해당하는 프로젝트만 조회됩니다."""
    evaluator_id = request.args.get("evaluator_id", type=int)
    if evaluator_id is None:
        return jsonify({"detail": "evaluator_id가 필요합니다."}), 400

    today_str = datetime.date.today().strftime('%Y-%m-%d')
    
    conn = db.get_db_connection()
    query = '''
        SELECT 
            a.id as assignment_id, 
            a.status, 
            p.id as project_id,
            p.title as project_title,
            e.id as employee_id, 
            e.name, 
            e.emp_id, 
            e.team_name, 
            e.position
        FROM evaluation_assignments a
        JOIN evaluation_projects p ON a.project_id = p.id
        JOIN employees e ON p.evaluatee_id = e.id
        WHERE a.evaluator_id = ?
          AND (
            p.start_date IS NULL 
            OR p.end_date IS NULL 
            OR ? BETWEEN p.start_date AND p.end_date
          )
        ORDER BY a.status DESC, e.name ASC
    '''
    rows = conn.execute(query, (evaluator_id, today_str)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@api_bp.route("/evaluations/questions", methods=["GET"])
def get_questions():
    """특정 배정 프로젝트의 평가 유형에 맞는 질문 목록을 반환합니다."""
    assignment_id = request.args.get("assignment_id", type=int)
    conn = db.get_db_connection()
    
    evaluation_type = '동료사원 평가'
    if assignment_id is not None:
        row = conn.execute('''
            SELECT p.evaluation_type 
            FROM evaluation_assignments a
            JOIN evaluation_projects p ON a.project_id = p.id
            WHERE a.id = ?
        ''', (assignment_id,)).fetchone()
        if row:
            evaluation_type = row['evaluation_type']
            
    rows = conn.execute('''
        SELECT * FROM evaluation_questions 
        WHERE is_active = 1 AND evaluation_type = ? 
        ORDER BY sort_order ASC, id ASC
    ''', (evaluation_type,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@api_bp.route("/evaluations/submit", methods=["POST"])
def submit_evaluation():
    """동료 사원에 대한 평가 결과를 최종 제출하고 배정 상태를 완료로 업데이트합니다. 기존 임시저장이 있으면 제거합니다."""
    data = request.get_json() or {}
    assignment_id = data.get("assignment_id")
    evaluator_id = data.get("evaluator_id")
    evaluatee_id = data.get("evaluatee_id")
    answers = data.get("answers") or []
    signature_data = data.get("signature_data")

    if assignment_id is None or evaluator_id is None or evaluatee_id is None:
        return jsonify({"detail": "필수 데이터가 누락되었습니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        # 1. 배정 존재 여부 및 상태 확인
        c.execute('SELECT id, status FROM evaluation_assignments WHERE id = ?', (assignment_id,))
        assignment = c.fetchone()
        if not assignment:
            return jsonify({"detail": "해당 평가 배정 정보를 찾을 수 없습니다."}), 404
        if assignment['status'] == 'completed':
            return jsonify({"detail": "이미 최종 제출 완료된 평가입니다. 수정할 수 없습니다."}), 400
            
        # 2. 기존 임시 저장 레코드가 있으면 삭제 (Cascade 적용으로 answers도 함께 연쇄 삭제됨)
        c.execute('DELETE FROM evaluations WHERE assignment_id = ?', (assignment_id,))
            
        # 3. evaluations 테이블에 마스터 데이터 등록
        c.execute('''
            INSERT INTO evaluations (assignment_id, evaluator_id, evaluatee_id, signature_data)
            VALUES (?, ?, ?, ?)
        ''', (assignment_id, evaluator_id, evaluatee_id, signature_data))
        evaluation_id = c.lastrowid
        
        # 4. evaluation_answers 테이블에 세부 문항별 답변 등록
        for answer in answers:
            q_id = answer.get("question_id")
            score = answer.get("score")
            answer_text = answer.get("answer_text")
            c.execute('''
                INSERT INTO evaluation_answers (evaluation_id, question_id, score, answer_text)
                VALUES (?, ?, ?, ?)
            ''', (evaluation_id, q_id, score, answer_text))
            
        # 5. 배정 상태 완료(completed) 처리
        c.execute('''
            UPDATE evaluation_assignments
            SET status = 'completed'
            WHERE id = ?
        ''', (assignment_id,))
        
        conn.commit()
        return jsonify({"success": True, "message": "평가가 성공적으로 최종 제출되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/evaluations/draft", methods=["POST"])
def save_evaluation_draft():
    """동료 사원에 대한 평가 내용을 임시 저장합니다. 기존 임시저장이 있으면 제거하고 다시 씁니다."""
    data = request.get_json() or {}
    assignment_id = data.get("assignment_id")
    evaluator_id = data.get("evaluator_id")
    evaluatee_id = data.get("evaluatee_id")
    answers = data.get("answers") or []

    if assignment_id is None or evaluator_id is None or evaluatee_id is None:
        return jsonify({"detail": "필수 데이터가 누락되었습니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        # 1. 배정 존재 여부 및 최종 제출 완료 상태 확인
        c.execute('SELECT id, status FROM evaluation_assignments WHERE id = ?', (assignment_id,))
        assignment = c.fetchone()
        if not assignment:
            return jsonify({"detail": "해당 평가 배정 정보를 찾을 수 없습니다."}), 404
        if assignment['status'] == 'completed':
            return jsonify({"detail": "이미 최종 제출 완료된 평가입니다. 임시 저장할 수 없습니다."}), 400
            
        # 2. 기존 임시 저장 레코드가 있으면 삭제
        c.execute('DELETE FROM evaluations WHERE assignment_id = ?', (assignment_id,))
            
        # 3. evaluations 테이블에 마스터 데이터 등록
        c.execute('''
            INSERT INTO evaluations (assignment_id, evaluator_id, evaluatee_id)
            VALUES (?, ?, ?)
        ''', (assignment_id, evaluator_id, evaluatee_id))
        evaluation_id = c.lastrowid
        
        # 4. evaluation_answers 테이블에 세부 문항별 답변 등록
        for answer in answers:
            q_id = answer.get("question_id")
            score = answer.get("score")
            answer_text = answer.get("answer_text")
            c.execute('''
                INSERT INTO evaluation_answers (evaluation_id, question_id, score, answer_text)
                VALUES (?, ?, ?, ?)
            ''', (evaluation_id, q_id, score, answer_text))
            
        # 5. 배정 상태 임시저장(saved) 처리
        c.execute('''
            UPDATE evaluation_assignments
            SET status = 'saved'
            WHERE id = ?
        ''', (assignment_id,))
        
        conn.commit()
        return jsonify({"success": True, "message": "평가 내용이 임시 저장되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/evaluations/draft", methods=["GET"])
def get_evaluation_draft():
    """특정 배정 건에 대해 기존 임시 저장된 답변 데이터를 조회하여 반환합니다."""
    assignment_id = request.args.get("assignment_id", type=int)
    if assignment_id is None:
        return jsonify({"detail": "assignment_id가 필요합니다."}), 400

    conn = db.get_db_connection()
    try:
        eval_row = conn.execute('SELECT id FROM evaluations WHERE assignment_id = ?', (assignment_id,)).fetchone()
        if not eval_row:
            return jsonify({"has_draft": False, "answers": []})
            
        evaluation_id = eval_row['id']
        rows = conn.execute('''
            SELECT question_id, score, answer_text 
            FROM evaluation_answers 
            WHERE evaluation_id = ?
        ''', (evaluation_id,)).fetchall()
        
        return jsonify({
            "has_draft": True,
            "answers": [dict(row) for row in rows]
        })
    finally:
        conn.close()

# --- 관리자(ADMIN) 전용 API ---

@api_bp.route("/admin/employees", methods=["GET"])
def admin_get_employees():
    """관리자용: 전체 사원 목록을 반환합니다."""
    return jsonify(db.get_all_employees())

@api_bp.route("/admin/employees", methods=["POST"])
def admin_create_employee():
    """관리자용: 개별 사원을 직접 등록합니다."""
    data = request.get_json() or {}
    emp_id = data.get("emp_id")
    name = data.get("name")
    team_name = data.get("team_name", "")
    position = data.get("position", "")
    phone = data.get("phone", "")

    if not emp_id or not name:
        return jsonify({"detail": "사번과 성명은 필수 항목입니다."}), 400

    emp_id = emp_id.strip()
    name = name.strip()
    if not emp_id or not name:
        return jsonify({"detail": "사번과 성명은 필수 항목입니다."}), 400

    if emp_id.upper() == 'ADMIN':
        return jsonify({"detail": "ADMIN은 예약된 사번입니다."}), 400

    success, msg = db.insert_single_employee(
        emp_id=emp_id,
        name=name,
        team_name=team_name.strip(),
        position=position.strip(),
        phone=phone.strip()
    )
    if not success:
        return jsonify({"detail": msg}), 400
    return jsonify({"message": msg})

@api_bp.route("/admin/employees/<string:emp_id>", methods=["PUT"])
def admin_update_employee(emp_id):
    """관리자용: 개별 사원의 정보를 수정합니다."""
    if not emp_id:
        return jsonify({"detail": "사번이 유효하지 않습니다."}), 400

    emp_id = emp_id.strip()
    if emp_id.upper() == 'ADMIN':
        return jsonify({"detail": "ADMIN 계정은 수정할 수 없습니다."}), 400

    data = request.get_json() or {}
    name = data.get("name")
    team_name = data.get("team_name", "")
    position = data.get("position", "")
    phone = data.get("phone", "")

    if not name or not name.strip():
        return jsonify({"detail": "성명은 필수 항목입니다."}), 400

    success, msg = db.update_employee_info(
        emp_id=emp_id,
        name=name.strip(),
        team_name=team_name.strip(),
        position=position.strip(),
        phone=phone.strip()
    )

    if not success:
        return jsonify({"detail": msg}), 400
    return jsonify({"success": True, "message": msg})

@api_bp.route("/admin/results/export", methods=["GET"])
def admin_export_results():
    """관리자용: 전체 평가 결과를 피벗 테이블 형식의 Excel 파일로 내보냅니다."""
    try:
        df = db.get_evaluation_results_for_export()
        
        # 파일 저장을 위한 바이너리 스트림 생성
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='평가결과집계')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='evaluation_results.xlsx'
        )
    except Exception as e:
        return jsonify({"detail": f"엑셀 생성 중 오류 발생: {str(e)}"}), 500

@api_bp.route("/admin/evaluations/<int:assignment_id>", methods=["GET"])
def admin_get_evaluation_detail(assignment_id):
    """관리자용: 특정 완료된 배정 건의 상세 답변 정보 및 서명 데이터를 조회합니다."""
    conn = db.get_db_connection()
    try:
        # 배정 정보 및 피평가자/평가자 정보
        assign_row = conn.execute('''
            SELECT 
                a.id as assignment_id, a.status,
                p.title as project_title,
                ee.name as evaluatee_name, ee.emp_id as evaluatee_emp_id, ee.team_name as evaluatee_team, ee.position as evaluatee_position,
                er.name as evaluator_name, er.emp_id as evaluator_emp_id, er.team_name as evaluator_team, er.position as evaluator_position
            FROM evaluation_assignments a
            JOIN evaluation_projects p ON a.project_id = p.id
            JOIN employees ee ON p.evaluatee_id = ee.id
            JOIN employees er ON a.evaluator_id = er.id
            WHERE a.id = ?
        ''', (assignment_id,)).fetchone()
        
        if not assign_row:
            return jsonify({"detail": "배정 정보를 찾을 수 없습니다."}), 404

        # 평가 및 서명 정보
        eval_row = conn.execute('''
            SELECT id, datetime(submitted_at, 'localtime') as submitted_at, signature_data 
            FROM evaluations 
            WHERE assignment_id = ?
        ''', (assignment_id,)).fetchone()

        answers = []
        submitted_at = None
        signature_data = None

        if eval_row:
            submitted_at = eval_row['submitted_at']
            signature_data = eval_row['signature_data']
            # 답변 목록 조회
            ans_rows = conn.execute('''
                SELECT question_id, score, answer_text 
                FROM evaluation_answers 
                WHERE evaluation_id = ?
            ''', (eval_row['id'],)).fetchall()
            answers = [dict(r) for r in ans_rows]

        # 질문 목록 전체 조회 (질문 순서대로 정렬)
        q_rows = conn.execute('''
            SELECT id as question_id, question_text, question_sub_text, category, is_essay, sort_order
            FROM evaluation_questions
            ORDER BY sort_order ASC
        ''').fetchall()
        
        questions = [dict(q) for q in q_rows]

        return jsonify({
            "assignment": dict(assign_row),
            "submitted_at": submitted_at,
            "signature_data": signature_data,
            "answers": answers,
            "questions": questions
        })
    finally:
        conn.close()

@api_bp.route("/admin/assignments", methods=["GET"])
def admin_get_assignments():
    """관리자용: 모든 동료 평가 배정 현황 목록을 반환합니다."""
    conn = db.get_db_connection()
    query = '''
        SELECT 
            a.id as assignment_id, 
            a.status,
            datetime(a.assigned_at, 'localtime') as assigned_at,
            a.project_id,
            p.title as project_title,
            er.id as evaluator_id,
            er.emp_id as evaluator_emp_id,
            er.name as evaluator_name,
            er.team_name as evaluator_team,
            er.position as evaluator_position,
            er.phone as evaluator_phone,
            ee.id as evaluatee_id,
            ee.emp_id as evaluatee_emp_id,
            ee.name as evaluatee_name,
            ee.team_name as evaluatee_team,
            ee.position as evaluatee_position
        FROM evaluation_assignments a
        JOIN evaluation_projects p ON a.project_id = p.id
        JOIN employees er ON a.evaluator_id = er.id
        JOIN employees ee ON p.evaluatee_id = ee.id
        ORDER BY a.assigned_at DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@api_bp.route("/admin/assignments", methods=["POST"])
def admin_create_assignment():
    """관리자용: 새로운 평가자 배정 관계를 추가합니다."""
    data = request.get_json() or {}
    evaluator_id = data.get("evaluator_id")
    evaluatee_id = data.get("evaluatee_id")
    project_id = data.get("project_id")
    evaluation_type = data.get("evaluation_type", "동료사원 평가")

    if evaluator_id is None:
        return jsonify({"detail": "평가자 ID가 필요합니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        if not project_id:
            if not evaluatee_id:
                return jsonify({"detail": "피평가자 ID 또는 프로젝트 ID가 필요합니다."}), 400
            
            if evaluator_id == evaluatee_id:
                return jsonify({"detail": "자기 자신을 평가 대상자로 배정할 수 없습니다."}), 400
                
            project_id = db.create_evaluation_project(evaluatee_id, evaluation_type)
        
        proj = c.execute('SELECT evaluatee_id FROM evaluation_projects WHERE id = ?', (project_id,)).fetchone()
        if not proj:
            return jsonify({"detail": "해당 평가 프로젝트를 찾을 수 없습니다."}), 404
        
        if proj['evaluatee_id'] == evaluator_id:
            return jsonify({"detail": "자기 자신을 평가 대상자로 배정할 수 없습니다."}), 400
        
        c.execute('''
            SELECT id FROM evaluation_assignments 
            WHERE project_id = ? AND evaluator_id = ?
        ''', (project_id, evaluator_id))
        exists = c.fetchone()
        
        if exists:
            return jsonify({"detail": "이미 배정된 동료 평가 관계입니다."}), 400
            
        c.execute('''
            INSERT INTO evaluation_assignments (project_id, evaluator_id)
            VALUES (?, ?)
        ''', (project_id, evaluator_id))
        conn.commit()
        return jsonify({"success": True, "message": "성공적으로 배정되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"detail": str(e)}), 400
    finally:
        conn.close()

@api_bp.route("/admin/projects", methods=["POST"])
def admin_create_project():
    """관리자용: 새로운 평가 프로젝트를 생성합니다."""
    data = request.get_json() or {}
    evaluatee_id = data.get("evaluatee_id")
    evaluation_type = data.get("evaluation_type", "동료사원 평가")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if evaluatee_id is None:
        return jsonify({"detail": "피평가자 ID가 필요합니다."}), 400

    try:
        project_id = db.create_evaluation_project(
            evaluatee_id,
            evaluation_type,
            start_date,
            end_date
        )
        return jsonify({"success": True, "project_id": project_id, "message": "평가 프로젝트가 생성되었습니다."})
    except Exception as e:
        return jsonify({"detail": str(e)}), 400

@api_bp.route("/admin/projects", methods=["GET"])
def admin_get_projects():
    """관리자용: 모든 평가 프로젝트 목록을 조회합니다."""
    try:
        return jsonify(db.get_all_projects())
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@api_bp.route("/admin/projects/<int:project_id>", methods=["DELETE"])
def admin_delete_project(project_id):
    """관리자용: 특정 평가 프로젝트를 삭제합니다."""
    try:
        db.delete_evaluation_project(project_id)
        return jsonify({"success": True, "message": "평가 프로젝트가 삭제되었습니다."})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@api_bp.route("/admin/assignments/<int:assignment_id>", methods=["DELETE"])
def admin_delete_assignment(assignment_id):
    """관리자용: 특정 평가 배정 관계를 삭제합니다."""
    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM evaluation_assignments WHERE id = ?', (assignment_id,))
        if c.rowcount == 0:
            return jsonify({"detail": "해당 배정 정보를 찾을 수 없습니다."}), 404
        conn.commit()
        return jsonify({"success": True, "message": "배정이 취소되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/upload-excel", methods=["POST"])
def admin_upload_excel():
    """관리자용: 사원명부 엑셀 파일을 업로드받아 DB에 일괄 반영합니다."""
    if 'file' not in request.files:
        return jsonify({"detail": "파일이 업로드되지 않았습니다."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"detail": "선택된 파일이 없습니다."}), 400

    # 업로드 임시 디렉토리 보장
    if platform.system() == 'Windows':
        temp_dir = r"C:\Users\user06065\Desktop\Code Test\Smart Evaluator Project\backend\temp"
    else:
        # 리눅스 환경 등에서는 현재 파일 위치 기준으로 temp 폴더 설정
        base_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    file_path = os.path.join(temp_dir, file.filename)
    file.save(file_path)
        
    try:
        # db.py의 파싱 및 upsert 로직 호출
        inserted, updated, skipped = db.upsert_employees_from_excel(file_path)
        msg = f"사원명부 업로드 완료: 신규 등록 {inserted}명, 정보 수정 {updated}명, 기존 동일 건너뜀 {skipped}명"
        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"detail": f"엑셀 처리 중 오류 발생: {str(e)}"}), 500
    finally:
        # 임시 파일 삭제
        if os.path.exists(file_path):
            os.remove(file_path)

@api_bp.route("/admin/assignments/bulk", methods=["POST"])
def admin_create_assignments_bulk():
    """관리자용: 특정 프로젝트에 다수의 평가자를 일괄 배정합니다."""
    data = request.get_json() or {}
    project_id = data.get("project_id")
    evaluator_ids = data.get("evaluator_ids") or []

    if project_id is None:
        return jsonify({"detail": "프로젝트 ID가 필요합니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        proj = c.execute('SELECT evaluatee_id FROM evaluation_projects WHERE id = ?', (project_id,)).fetchone()
        if not proj:
            return jsonify({"detail": "해당 평가 프로젝트를 찾을 수 없습니다."}), 404
        
        evaluatee_id = proj['evaluatee_id']
        added_count = 0
        
        for evaluator_id in evaluator_ids:
            if evaluator_id == evaluatee_id:
                continue  # 자기 자신은 배정에서 제외
            
            c.execute('''
                SELECT id FROM evaluation_assignments 
                WHERE project_id = ? AND evaluator_id = ?
            ''', (project_id, evaluator_id))
            exists = c.fetchone()
            
            if not exists:
                c.execute('''
                    INSERT INTO evaluation_assignments (project_id, evaluator_id)
                    VALUES (?, ?)
                ''', (project_id, evaluator_id))
                added_count += 1
        
        conn.commit()
        return jsonify({"success": True, "message": f"{added_count}명의 평가자가 성공적으로 추가되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/last-upload-time", methods=["GET"])
def admin_get_last_upload_time():
    """관리자용: 최근 사원명부 엑셀 업로드 시간을 반환합니다."""
    try:
        last_time = db.get_setting('last_upload_time', '업로드 기록 없음')
        return jsonify({"last_upload_time": last_time})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@api_bp.route("/common/upload-status", methods=["GET"])
def common_get_upload_status():
    """공통: 최근 사원명부 엑셀 업로드 시간과 총 사원 수를 반환합니다."""
    conn = db.get_db_connection()
    try:
        # 1. 총 사원 수 계산
        row = conn.execute('SELECT COUNT(*) as count FROM employees').fetchone()
        total_employees = row['count'] if row else 0
        
        # 2. 최근 업로드 일시 가져오기
        last_time = db.get_setting('last_upload_time', '')
        
        return jsonify({
            "last_upload_time": last_time,
            "total_employees": total_employees,
            "has_data": total_employees > 0 and bool(last_time)
        })
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
    finally:
        conn.close()

@api_bp.route("/admin/projects/<int:project_id>/period", methods=["PATCH"])
def admin_update_project_period(project_id):
    """관리자용: 특정 프로젝트의 평가 기간을 수정합니다."""
    data = request.get_json() or {}
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not start_date or not end_date:
        return jsonify({"detail": "시작일과 종료일이 필요합니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        # 프로젝트 존재 여부 확인
        proj = c.execute('SELECT id FROM evaluation_projects WHERE id = ?', (project_id,)).fetchone()
        if not proj:
            return jsonify({"detail": "해당 평가 프로젝트를 찾을 수 없습니다."}), 404
        
        c.execute('''
            UPDATE evaluation_projects
            SET start_date = ?, end_date = ?
            WHERE id = ?
        ''', (start_date, end_date, project_id))
        
        conn.commit()
        return jsonify({"success": True, "message": "평가 기간이 성공적으로 수정되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/questions", methods=["GET"])
def admin_get_questions():
    """관리자용: 모든 평가 문항 목록(비활성 포함)을 반환합니다."""
    conn = db.get_db_connection()
    rows = conn.execute('SELECT * FROM evaluation_questions ORDER BY sort_order ASC, id ASC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@api_bp.route("/admin/questions", methods=["POST"])
def admin_create_question():
    """관리자용: 새로운 평가 문항을 추가합니다."""
    data = request.get_json() or {}
    question_text = data.get("question_text")
    question_sub_text = data.get("question_sub_text", "")
    category = data.get("category")
    is_essay = data.get("is_essay")
    evaluation_type = data.get("evaluation_type", "동료사원 평가")

    if not question_text or is_essay is None or not category:
        return jsonify({"detail": "필수 데이터가 누락되었습니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        # 기존 최댓값 sort_order 조회
        max_order_row = c.execute('SELECT MAX(sort_order) as max_order FROM evaluation_questions').fetchone()
        max_order = max_order_row['max_order'] if max_order_row and max_order_row['max_order'] else 0

        c.execute('''
            INSERT INTO evaluation_questions (question_text, question_sub_text, category, is_essay, sort_order, is_active, evaluation_type)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        ''', (question_text.strip(), question_sub_text.strip() if question_sub_text else "", category.strip(), is_essay, max_order + 1, evaluation_type))
        conn.commit()
        return jsonify({"success": True, "message": "새로운 평가 문항이 추가되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/questions/<int:question_id>", methods=["PUT"])
def admin_update_question(question_id):
    """관리자용: 특정 평가 문항을 수정합니다."""
    data = request.get_json() or {}
    question_text = data.get("question_text")
    question_sub_text = data.get("question_sub_text", "")
    category = data.get("category")
    is_essay = data.get("is_essay")
    evaluation_type = data.get("evaluation_type", "동료사원 평가")

    if not question_text or is_essay is None or not category:
        return jsonify({"detail": "필수 데이터가 누락되었습니다."}), 400

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        # 존재 여부 확인
        q = c.execute('SELECT id FROM evaluation_questions WHERE id = ?', (question_id,)).fetchone()
        if not q:
            return jsonify({"detail": "해당 평가 문항을 찾을 수 없습니다."}), 404
            
        c.execute('''
            UPDATE evaluation_questions
            SET question_text = ?, question_sub_text = ?, category = ?, is_essay = ?, evaluation_type = ?
            WHERE id = ?
        ''', (question_text.strip(), question_sub_text.strip() if question_sub_text else "", category.strip(), is_essay, evaluation_type, question_id))
        conn.commit()
        return jsonify({"success": True, "message": "평가 문항이 성공적으로 수정되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/questions/<int:question_id>", methods=["DELETE"])
def admin_delete_question(question_id):
    """관리자용: 특정 평가 문항을 삭제(비활성화)합니다."""
    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        # 기 제출된 답변(evaluation_answers)이 존재하는지 확인
        ans_exists = c.execute('SELECT id FROM evaluation_answers WHERE question_id = ? LIMIT 1', (question_id,)).fetchone()
        if ans_exists:
            # 답변이 이미 존재하면 비활성화(Soft Delete) 처리
            c.execute('UPDATE evaluation_questions SET is_active = 0 WHERE id = ?', (question_id,))
            msg = "해당 문항에 대한 기 제출된 답변이 존재하여, 안전을 위해 문항을 '비활성화' 처리하였습니다."
        else:
            # 답변이 없으면 데이터베이스에서 Hard Delete
            c.execute('DELETE FROM evaluation_questions WHERE id = ?', (question_id,))
            msg = "평가 문항이 데이터베이스에서 영구 삭제되었습니다."
            
        conn.commit()
        return jsonify({"success": True, "message": msg})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/questions/<int:question_id>/activate", methods=["PATCH"])
def admin_activate_question(question_id):
    """관리자용: 특정 비활성화된 평가 문항을 다시 활성화합니다."""
    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE evaluation_questions SET is_active = 1 WHERE id = ?', (question_id,))
        conn.commit()
        return jsonify({"success": True, "message": "평가 문항이 다시 활성화되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/questions/reorder", methods=["PATCH"])
def admin_reorder_questions():
    """관리자용: 평가 문항들의 순서(sort_order)를 일괄 조정합니다."""
    data = request.get_json() or {}
    question_ids = data.get("question_ids") or []

    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        for index, q_id in enumerate(question_ids):
            c.execute('''
                UPDATE evaluation_questions
                SET sort_order = ?
                WHERE id = ?
            ''', (index + 1, q_id))
        conn.commit()
        return jsonify({"success": True, "message": "문항 순서가 변경되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()

@api_bp.route("/admin/assignments/<int:assignment_id>/status", methods=["PATCH"])
def admin_update_assignment_status(assignment_id):
    """관리자용: 특정 평가 배정 건의 진행 상태를 변경합니다."""
    data = request.get_json() or {}
    status = data.get("status")

    if not status:
        return jsonify({"detail": "상태 값이 누락되었습니다."}), 400

    status_val = status.strip().lower()
    if status_val not in ['pending', 'saved', 'completed']:
        return jsonify({"detail": "유효하지 않은 상태 값입니다. (pending, saved, completed 중 선택)"}), 400
        
    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        assignment = c.execute('SELECT id FROM evaluation_assignments WHERE id = ?', (assignment_id,)).fetchone()
        if not assignment:
            return jsonify({"detail": "해당 배정 정보를 찾을 수 없습니다."}), 404
            
        c.execute('''
            UPDATE evaluation_assignments
            SET status = ?
            WHERE id = ?
        ''', (status_val, assignment_id))
        conn.commit()
        return jsonify({"success": True, "message": f"배정 상태가 '{status_val}'(으)로 성공적으로 변경되었습니다."})
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({"detail": f"데이터베이스 오류: {str(e)}"}), 500
    finally:
        conn.close()
