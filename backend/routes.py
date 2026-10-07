from flask import Blueprint, request, jsonify, send_file
import os
import tempfile
import io
import db
import pandas as pd
import sqlite3
import datetime
import platform
from records import (EvaluationError, assignment_info, evaluation_detail, project_questions,
                     question_revision, save_evaluation, validate_period, today)


api_bp = Blueprint('api', __name__)

@api_bp.before_request
def protect_write_window():
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        if os.path.exists(db.DB_PATH + '.maintenance'):
            return jsonify({"detail": "자료 보존을 위한 점검 중입니다. 잠시 후 다시 시도해 주세요."}), 503
        # Login also records consent, so it must honor the write-stop window.
        # Its authentication, request format and token behavior are unchanged.
        if request.path == '/api/auth/login':
            return None
        if request.headers.get('X-App-Version') != '2':
            return jsonify({"detail": "프로그램이 업데이트되었습니다. 화면을 새로고침한 후 다시 시도해 주세요."}), 409


def evaluation_write(final):
    conn = db.get_db_connection()
    try:
        save_evaluation(conn, request.get_json(silent=True), final=final)
        return jsonify({"success": True, "message": "평가가 최종 제출되었습니다." if final else "평가 내용이 임시 저장되었습니다."})
    except EvaluationError as error:
        conn.rollback()
        return jsonify({"detail": str(error)}), error.status
    except sqlite3.Error:
        conn.rollback()
        return jsonify({"detail": "평가 저장 중 오류가 발생했습니다. 입력 내용은 이전 상태로 보존되었습니다."}), 500
    finally:
        conn.close()


@api_bp.route('/admin/rounds', methods=['GET', 'POST'])
def admin_rounds():
    conn = db.get_db_connection()
    try:
        if request.method == 'GET':
            return jsonify([dict(r) for r in conn.execute('SELECT id,name FROM evaluation_rounds ORDER BY id DESC')])
        data = request.get_json(silent=True)
        name = data.get('name') if isinstance(data, dict) else None
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
            return jsonify({"detail": "평가 회차 이름을 100자 이내로 입력해 주세요."}), 400
        cursor = conn.execute('INSERT INTO evaluation_rounds(name) VALUES (?)', (name.strip(),))
        conn.commit()
        return jsonify({"success": True, "round_id": cursor.lastrowid})
    except sqlite3.IntegrityError:
        conn.rollback()
        return jsonify({"detail": "이미 존재하는 평가 회차입니다."}), 400
    finally:
        conn.close()


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
        # 로그인 시마다 개인정보 동의 일시 기록 갱신
        db.update_privacy_agreement(emp_id)
        
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

    today_str = today()
    
    conn = db.get_db_connection()
    query = '''
        SELECT 
            a.id as assignment_id, 
            a.status, 
            p.id as project_id,
            p.title as project_title,
            p.round_id, r.name AS round_name, p.evaluation_type,
            e.id as employee_id, 
            e.name, 
            e.emp_id, 
            e.team_name, 
            e.position
        FROM evaluation_assignments a
        JOIN evaluation_projects p ON a.project_id = p.id
        JOIN employees e ON p.evaluatee_id = e.id
        JOIN evaluation_rounds r ON r.id = p.round_id
        WHERE a.evaluator_id = ?
          AND p.status = 'active'
          AND (p.start_date IS NULL OR p.start_date = '' OR p.start_date <= ?)
          AND (p.end_date IS NULL OR p.end_date = '' OR p.end_date >= ?)
        ORDER BY a.status DESC, e.name ASC
    '''
    rows = conn.execute(query, (evaluator_id, today_str, today_str)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@api_bp.route("/evaluations/questions", methods=["GET"])
def get_questions():
    assignment_id = request.args.get("assignment_id", type=int)
    if assignment_id is None:
        return jsonify({"detail": "assignment_id가 필요합니다."}), 400
    conn = db.get_db_connection()
    try:
        info = assignment_info(conn, assignment_id)
        questions = project_questions(conn, info['project_id'])
        revision = question_revision(questions)
        return jsonify([{**q, 'question_revision': revision} for q in questions])
    except EvaluationError as error:
        return jsonify({"detail": str(error)}), error.status
    finally:
        conn.close()

@api_bp.route("/evaluations/submit", methods=["POST"])
def submit_evaluation():
    return evaluation_write(final=True)

@api_bp.route("/evaluations/draft", methods=["POST"])
def save_evaluation_draft():
    return evaluation_write(final=False)

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
    existing = db.get_employee_by_emp_id(emp_id)
    if not existing:
        return jsonify({"detail": "사원을 찾을 수 없습니다."}), 404
    team_name = data.get("team_name", existing.get("team_name") or "")
    position = data.get("position", existing.get("position") or "")
    phone = data.get("phone")
    if phone is not None and not isinstance(phone, str):
        return jsonify({"detail": "전화번호는 문자열이어야 합니다."}), 400

    if not isinstance(name, str) or not name.strip():
        return jsonify({"detail": "성명은 필수 항목입니다."}), 400
    if not isinstance(team_name, str) or not isinstance(position, str):
        return jsonify({"detail": "소속과 직급은 문자열이어야 합니다."}), 400

    success, msg = db.update_employee_info(
        emp_id=emp_id,
        name=name.strip(),
        team_name=team_name.strip(),
        position=position.strip(),
        phone=phone.strip() if phone is not None else None
    )

    if not success:
        return jsonify({"detail": msg}), 400
    return jsonify({"success": True, "message": msg})

@api_bp.route("/admin/employees/reset", methods=["POST"])
def admin_reset_employees():
    """관리자용: 모든 사원 정보 및 관련 평가 데이터를 일괄 초기화합니다."""
    success, msg = db.delete_all_employees()
    if not success:
        return jsonify({"detail": msg}), 409
    return jsonify({"success": True, "message": msg})

@api_bp.route("/admin/results/export", methods=["GET"])
def admin_export_results():
    """배정별 결과와 고정된 문항·인적사항을 Excel 파일로 내보냅니다."""
    try:
        df = db.get_evaluation_results_for_export()
        
        # 파일 저장을 위한 바이너리 스트림 생성
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='평가결과집계')
            for row in writer.sheets['평가결과집계'].iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        cell.data_type = 's'
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
    conn = db.get_db_connection()
    try:
        conn.execute('BEGIN')
        return jsonify(evaluation_detail(conn, assignment_id))
    except EvaluationError as error:
        return jsonify({"detail": str(error)}), error.status
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
                
            project_id = db.create_evaluation_project(evaluatee_id, evaluation_type, round_id=data.get("round_id"))
        
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
            end_date,
            round_id=data.get("round_id")
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
    except ValueError as e:
        return jsonify({"detail": str(e)}), 409
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

@api_bp.route("/admin/assignments/<int:assignment_id>", methods=["DELETE"])
def admin_delete_assignment(assignment_id):
    """관리자용: 특정 평가 배정 관계를 삭제합니다."""
    conn = db.get_db_connection()
    c = conn.cursor()
    try:
        conn.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT id FROM evaluations WHERE assignment_id=?', (assignment_id,)).fetchone():
            return jsonify({'detail': '평가 기록이 있는 배정은 삭제할 수 없습니다.'}), 409
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
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"detail": "엑셀 파일을 선택해 주세요."}), 400
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in ('.xls', '.xlsx'):
        return jsonify({"detail": "xls 또는 xlsx 파일만 사용할 수 있습니다."}), 400
    preview = request.args.get('preview') == '1'
    token = request.form.get('preview_token')
    if not preview and not token:
        return jsonify({"detail": "명부 미리보기를 먼저 확인해 주세요."}), 409
    # Never use user-controlled filenames as a filesystem path.
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    descriptor, file_path = tempfile.mkstemp(suffix=suffix, dir=temp_dir)
    os.close(descriptor)
    try:
        file.save(file_path)
        if preview:
            return jsonify(db.preview_employees_from_excel(file_path))
        inserted, updated, skipped = db.upsert_employees_from_excel(file_path, preview_token=token)
        return jsonify({"success": True, "message": f"명부 반영 완료: 신규 {inserted}명, 수정 {updated}명, 동일 {skipped}명"})
    except ValueError as error:
        return jsonify({"detail": str(error)}), 400
    except Exception:
        return jsonify({"detail": "명부를 처리하지 못했습니다. 파일 양식을 확인해 주세요. 기존 자료는 보존되었습니다."}), 400
    finally:
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

    try:
        validate_period(start_date, end_date)
    except EvaluationError as error:
        return jsonify({"detail": str(error)}), 400
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
        snapshot_exists = c.execute('SELECT question_id FROM project_question_snapshots WHERE question_id=? LIMIT 1', (question_id,)).fetchone()
        if ans_exists or snapshot_exists:
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
        conn.execute('BEGIN IMMEDIATE')
        final_record = c.execute('SELECT id FROM evaluations WHERE assignment_id=? AND (finalized_at IS NOT NULL OR record_snapshot IS NOT NULL)', (assignment_id,)).fetchone()
        if final_record and status_val != 'completed':
            return jsonify({'detail': '최종 제출된 평가의 상태는 되돌릴 수 없습니다. 새 회차를 생성해 주세요.'}), 409
        if not final_record and status_val == 'completed':
            return jsonify({'detail': '평가자의 유효한 최종 제출 후에만 완료 처리할 수 있습니다.'}), 409
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
