"""Frozen evaluation records and server-side submission rules (no login changes)."""
import base64
import binascii
import hashlib
import json
import struct
from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SIGNATURE_PREFIX = 'data:image/png;base64,'


class EvaluationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def today():
    return datetime.now(KST).date().isoformat()


def validate_period(start, end):
    for value in (start, end):
        if value is not None and value != '':
            if not isinstance(value, str):
                raise EvaluationError('평가 기간은 YYYY-MM-DD 형식이어야 합니다.')
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except ValueError:
                raise EvaluationError('평가 기간은 YYYY-MM-DD 형식이어야 합니다.') from None
    if start and end and start > end:
        raise EvaluationError('종료일은 시작일보다 빠를 수 없습니다.')


def positive_int(value, label):
    if type(value) is not int or value < 1:
        raise EvaluationError(f'{label} 값이 올바르지 않습니다.')
    return value


def freeze_project_questions(conn, project_id, legacy=False):
    project = conn.execute('SELECT evaluation_type FROM evaluation_projects WHERE id=?', (project_id,)).fetchone()
    questions = conn.execute('SELECT * FROM evaluation_questions WHERE evaluation_type=? AND is_active=1 ORDER BY sort_order,id', (project['evaluation_type'],)).fetchall()
    if legacy:
        known = {r['id'] for r in questions}
        extra = conn.execute('''SELECT DISTINCT q.* FROM evaluation_questions q
            JOIN evaluation_answers ans ON ans.question_id=q.id
            JOIN evaluations ev ON ev.id=ans.evaluation_id
            JOIN evaluation_assignments a ON a.id=ev.assignment_id
            WHERE a.project_id=? AND q.evaluation_type=?''', (project_id, project['evaluation_type'])).fetchall()
        questions = list(questions) + [q for q in extra if q['id'] not in known]
    for q in questions:
        conn.execute('''INSERT OR IGNORE INTO project_question_snapshots
            (project_id,question_id,question_text,question_sub_text,category,is_essay,sort_order,min_score,max_score)
            VALUES (?,?,?,?,?,?,?,?,?)''', (project_id, q['id'], q['question_text'], q['question_sub_text'],
                                         q['category'], q['is_essay'], q['sort_order'], 6, 10))


def project_questions(conn, project_id):
    return [dict(r) for r in conn.execute('''SELECT question_id, question_id AS id,
        question_text,question_sub_text,category,is_essay,sort_order,min_score,max_score
        FROM project_question_snapshots WHERE project_id=? ORDER BY sort_order,question_id''', (project_id,))]


def question_revision(questions):
    return hashlib.sha256(json.dumps(questions, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def assignment_info(conn, assignment_id):
    row = conn.execute('''SELECT a.id AS assignment_id,a.status,a.evaluator_id,
        p.id AS project_id,p.title AS project_title,p.evaluatee_id,p.evaluation_type,
        p.round_id,r.name AS round_name,p.status AS project_status,p.start_date,p.end_date,
        ee.name AS evaluatee_name,ee.emp_id AS evaluatee_emp_id,ee.team_name AS evaluatee_team,
        ee.position AS evaluatee_position,er.name AS evaluator_name,er.emp_id AS evaluator_emp_id,
        er.team_name AS evaluator_team,er.position AS evaluator_position
        FROM evaluation_assignments a JOIN evaluation_projects p ON p.id=a.project_id
        JOIN evaluation_rounds r ON r.id=p.round_id
        JOIN employees ee ON ee.id=p.evaluatee_id JOIN employees er ON er.id=a.evaluator_id
        WHERE a.id=?''', (assignment_id,)).fetchone()
    if not row:
        raise EvaluationError('해당 평가 배정 정보를 찾을 수 없습니다.', 404)
    return dict(row)


def answers_for(conn, evaluation_id):
    return [dict(r) for r in conn.execute('SELECT id AS answer_id,question_id,score,answer_text FROM evaluation_answers WHERE evaluation_id=? ORDER BY id', (evaluation_id,))]


def capture_record(conn, assignment_id, source='submitted', evaluation_id=None):
    info = assignment_info(conn, assignment_id)
    row = conn.execute('SELECT * FROM evaluations WHERE assignment_id=?', (assignment_id,)).fetchone()
    if evaluation_id is not None and (not row or row['id'] != evaluation_id):
        raise RuntimeError('평가 기록 연결을 확인할 수 없습니다.')
    answers = answers_for(conn, row['id']) if row else []
    if source == 'legacy':
        # The original questionnaire/scale cannot be reconstructed with certainty.
        # Freeze only the question IDs actually answered, including inactive ones.
        ids = {a['question_id'] for a in answers}
        questions = []
        for q in conn.execute('SELECT * FROM evaluation_questions ORDER BY sort_order,id'):
            if q['id'] in ids:
                questions.append({**dict(q), 'question_id': q['id'], 'min_score': None, 'max_score': None})
    else:
        questions = project_questions(conn, info['project_id'])
    note = '이전 당시 DB의 문항·인적사항을 보존했습니다. 원래 문항 버전과 점수 척도는 확인되지 않았습니다.' if source == 'legacy' else ''
    if source == 'legacy' and any(q.get('evaluation_type') != info['evaluation_type'] for q in questions):
        note += ' 기존 답변에 다른 평가 유형의 문항이 포함되어 있습니다. 원본 답변은 삭제하지 않았습니다.'
    if len({answer['question_id'] for answer in answers}) != len(answers):
        note += ' 기존 자료에 같은 문항의 답변이 여러 건 있습니다. 각 답변과 점수 합계를 보존했습니다.'
    if row and (row['evaluator_id'] != info['evaluator_id'] or row['evaluatee_id'] != info['evaluatee_id']):
        note += ' 기존 제출의 사원 ID가 배정 정보와 다릅니다. 원본 ID는 보존되었습니다.'
    return {'assignment': info, 'questions': questions, 'answers': answers,
            'source': source, 'note': note, 'captured_at': datetime.now(timezone.utc).isoformat()}


def korea_timestamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)  # SQLite CURRENT_TIMESTAMP
    return parsed.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S')


def evaluation_detail(conn, assignment_id):
    info = assignment_info(conn, assignment_id)
    row = conn.execute('SELECT * FROM evaluations WHERE assignment_id=?', (assignment_id,)).fetchone()
    if row and row['record_snapshot']:
        snapshot = json.loads(row['record_snapshot'])
        info = snapshot['assignment']
        questions = snapshot['questions']
        answers = snapshot['answers']
        source, note = snapshot['source'], snapshot['note']
    else:
        questions = project_questions(conn, info['project_id'])
        answers = answers_for(conn, row['id']) if row else []
        source, note = 'project', ''
    objective_ids = {q['question_id'] for q in questions if not q['is_essay']}
    scores = [a['score'] for a in answers if a['question_id'] in objective_ids and isinstance(a['score'], (int, float))]
    maximums = [q['max_score'] for q in questions if not q['is_essay']]
    return {'assignment': info, 'submitted_at': korea_timestamp(row['submitted_at']) if row else None,
            'signature_data': row['signature_data'] if row else None, 'questions': questions, 'answers': answers,
            'total_score': sum(scores) if scores else None,
            'max_score': sum(maximums) if maximums and all(x is not None for x in maximums) else None,
            'snapshot_source': source, 'snapshot_note': note}


def validate_signature(value):
    if not isinstance(value, str) or not value.startswith(SIGNATURE_PREFIX) or len(value) > 750_000:
        raise EvaluationError('올바른 PNG 서명이 필요합니다.')
    try:
        image = base64.b64decode(value[len(SIGNATURE_PREFIX):], validate=True)
        if not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image) < 45:
            raise ValueError()
        width, height = struct.unpack('>II', image[16:24])
        if not 1 <= width <= 2048 or not 1 <= height <= 2048:
            raise ValueError()
        # Decode rather than just accepting PNG magic bytes; reject broken images.
        from PIL import Image, ImageChops
        import io
        with Image.open(io.BytesIO(image)) as png:
            if png.format != 'PNG':
                raise ValueError()
            png.verify()
        with Image.open(io.BytesIO(image)) as png:
            background = Image.new('RGBA', png.size, 'white')
            visible = Image.alpha_composite(background, png.convert('RGBA')).convert('RGB')
            if ImageChops.difference(visible, Image.new('RGB', visible.size, 'white')).getbbox() is None:
                raise ValueError()
    except (ValueError, binascii.Error, struct.error, OSError):
        raise EvaluationError('서명 이미지가 손상되었거나 올바르지 않습니다.') from None


def save_evaluation(conn, data, final=False):
    if not isinstance(data, dict):
        raise EvaluationError('요청은 JSON 객체여야 합니다.')
    assignment_id = positive_int(data.get('assignment_id'), '배정 ID')
    evaluator_id = positive_int(data.get('evaluator_id'), '평가자 ID')
    evaluatee_id = positive_int(data.get('evaluatee_id'), '피평가자 ID')
    conn.execute('BEGIN IMMEDIATE')  # Serialize status check and write; no completed overwrite race.
    info = assignment_info(conn, assignment_id)
    if evaluator_id != info['evaluator_id'] or evaluatee_id != info['evaluatee_id']:
        raise EvaluationError('평가자·피평가자 정보가 배정과 일치하지 않습니다.')
    row = conn.execute('SELECT * FROM evaluations WHERE assignment_id=?', (assignment_id,)).fetchone()
    if info['status'] == 'completed' or (row and (row['finalized_at'] or row['record_snapshot'])):
        raise EvaluationError('최종 제출된 평가는 수정할 수 없습니다.', 409)
    validate_period(info['start_date'], info['end_date'])
    if info['project_status'] != 'active' or (info['start_date'] and today() < info['start_date']) or (info['end_date'] and today() > info['end_date']):
        raise EvaluationError('현재 평가 기간이 아닙니다.', 409)
    questions = project_questions(conn, info['project_id'])
    if not questions:
        raise EvaluationError('이 프로젝트에 등록된 평가 문항이 없습니다.')
    revision = data.get('question_revision')
    if revision != question_revision(questions):
        raise EvaluationError('평가 화면을 새로고침한 후 저장해 주세요.', 409)
    answers = data.get('answers')
    if not isinstance(answers, list):
        raise EvaluationError('답변 목록이 올바르지 않습니다.')
    expected = {q['question_id']: q for q in questions}
    seen = set()
    cleaned = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise EvaluationError('답변 항목이 올바르지 않습니다.')
        qid = positive_int(answer.get('question_id'), '문항 ID')
        if qid in seen or qid not in expected:
            raise EvaluationError('중복 문항 또는 이 프로젝트에 속하지 않은 문항이 있습니다.')
        seen.add(qid)
        question = expected[qid]
        score = answer.get('score')
        text = answer.get('answer_text', '')
        if text is None:
            text = ''
        if not isinstance(text, str) or len(text) > 1000:
            raise EvaluationError('서술형 답변은 1,000자 이내의 문자열이어야 합니다.')
        if question['is_essay']:
            if score is not None:
                raise EvaluationError('서술형 문항에 점수를 지정할 수 없습니다.')
            if final and not text.strip():
                raise EvaluationError('모든 서술형 문항에 답변해 주세요.')
        else:
            if text.strip():
                raise EvaluationError('객관식 문항에 서술형 답변을 지정할 수 없습니다.')
            if score is not None and (type(score) is not int or not question['min_score'] <= score <= question['max_score']):
                raise EvaluationError('객관식 점수가 허용된 척도를 벗어났습니다.')
            if final and score is None:
                raise EvaluationError('모든 객관식 문항에 답변해 주세요.')
        cleaned.append((qid, score, text))
    if final and seen != set(expected):
        raise EvaluationError('모든 평가 문항에 답변해 주세요.')
    if final:
        validate_signature(data.get('signature_data'))
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    if row:
        evaluation_id = row['id']
        conn.execute('UPDATE evaluations SET signature_data=?,submitted_at=? WHERE id=?', (data.get('signature_data') if final else None, timestamp, evaluation_id))
        conn.execute('DELETE FROM evaluation_answers WHERE evaluation_id=?', (evaluation_id,))
    else:
        evaluation_id = conn.execute('INSERT INTO evaluations(assignment_id,evaluator_id,evaluatee_id,signature_data,submitted_at) VALUES (?,?,?,?,?)',
                                     (assignment_id, info['evaluator_id'], info['evaluatee_id'], data.get('signature_data') if final else None, timestamp)).lastrowid
    for qid, score, text in cleaned:
        conn.execute('INSERT INTO evaluation_answers(evaluation_id,question_id,score,answer_text) VALUES (?,?,?,?)', (evaluation_id, qid, score, text))
    conn.execute('UPDATE evaluation_assignments SET status=? WHERE id=?', ('completed' if final else 'saved', assignment_id))
    if final:
        snapshot = capture_record(conn, assignment_id)
        conn.execute('UPDATE evaluations SET finalized_at=?,record_snapshot=? WHERE id=?', (timestamp, json.dumps(snapshot, ensure_ascii=False), evaluation_id))
    conn.commit()
    return evaluation_id


def export_results(conn):
    """One row per assignment; stable question IDs/versions, no pivot dropna."""
    import pandas as pd
    base_columns = ['배정 ID', '프로젝트 ID', '평가 회차', '평가 종류', '프로젝트명',
                    '피평가자 사번', '피평가자 성명', '피평가자 부서', '피평가자 직급',
                    '평가자 사번', '평가자 성명', '평가자 부서', '평가자 직급', '배정 상태',
                    '제출 일시', '평가 총점', '객관식 만점', '자료 출처', '자료 비고']
    rows = []
    question_columns = []
    for assignment in conn.execute('SELECT id,status FROM evaluation_assignments ORDER BY project_id,id').fetchall():
        detail = evaluation_detail(conn, assignment['id'])
        info = detail['assignment']
        row = dict(zip(base_columns, [assignment['id'], info['project_id'], info['round_name'], info['evaluation_type'],
            info['project_title'], info['evaluatee_emp_id'], info['evaluatee_name'], info['evaluatee_team'] or '',
            info['evaluatee_position'] or '', info['evaluator_emp_id'], info['evaluator_name'], info['evaluator_team'] or '',
            info['evaluator_position'] or '', {'pending':'대기','saved':'임시 저장','completed':'완료'}.get(assignment['status'], assignment['status']),
            detail['submitted_at'] or '', detail['total_score'], detail['max_score'],
            '기존 자료' if detail['snapshot_source']=='legacy' else '고정 문항', detail['snapshot_note']]))
        for question in detail['questions']:
            # Include version identity: editing a template with the same ID/text
            # cannot merge different historical questionnaires into one column.
            version = hashlib.sha256(json.dumps({k:question.get(k) for k in
                ('question_text','question_sub_text','category','is_essay','min_score','max_score')},
                sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:8]
            label = f"[Q{question['question_id']} {version}] {question['question_text']}"
            if label not in question_columns:
                question_columns.append(label)
            values = [a['answer_text'] if question['is_essay'] else a['score'] for a in detail['answers'] if a['question_id']==question['question_id']]
            row[label] = values[0] if len(values)==1 else ' | '.join('' if v is None else str(v) for v in values)
        rows.append(row)
    return pd.DataFrame(rows, columns=base_columns + question_columns)
