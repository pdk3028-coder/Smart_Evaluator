import { useState } from 'react';
import { apiFetch } from '../api';
import './QuestionManager.css';

const typeOf = (question) => question.evaluation_type || '동료사원 평가';

async function request(path, options = {}) {
  const response = await apiFetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || '요청을 처리하지 못했습니다.');
  return data;
}

function QuestionManager({ questions, evaluationTypes, onRefresh, loading, dataError }) {
  const [typeChoice, setTypeChoice] = useState('');
  const [dialog, setDialog] = useState(null);
  const [typeName, setTypeName] = useState('');
  const [startMode, setStartMode] = useState('empty');
  const [sourceType, setSourceType] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ category: '', question_text: '', question_sub_text: '', is_essay: 0, evaluation_type: '' });
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const selectedType = evaluationTypes.includes(typeChoice) ? typeChoice : (evaluationTypes[0] || '');
  const selectedQuestions = questions.filter((question) => typeOf(question) === selectedType);
  const activeCount = selectedQuestions.filter((question) => question.is_active).length;

  const openTypeDialog = () => {
    setTypeName('');
    setStartMode('empty');
    setSourceType(selectedType);
    setDialogError('');
    setDialog('type');
  };

  const openQuestionDialog = (question = null) => {
    setEditingId(question?.id ?? null);
    setForm(question ? {
      category: question.category || '',
      question_text: question.question_text || '',
      question_sub_text: question.question_sub_text || '',
      is_essay: Number(question.is_essay),
      evaluation_type: typeOf(question),
    } : { category: '', question_text: '', question_sub_text: '', is_essay: 0, evaluation_type: selectedType });
    setDialogError('');
    setDialog('question');
  };

  const closeDialog = () => {
    if (!busy) {
      setDialog(null);
      setDialogError('');
    }
  };

  const refreshAfterChange = async (message) => {
    const refreshed = await onRefresh();
    setNotice(refreshed ? message : '저장했지만 목록을 다시 불러오지 못했습니다. 새로고침해 주세요.');
  };

  const createType = async (event) => {
    event.preventDefault();
    const name = typeName.trim();
    if (!name) return setDialogError('평가 종류 이름을 입력해 주세요.');
    if (startMode === 'copy' && !sourceType) return setDialogError('복사할 평가 종류를 선택해 주세요.');
    setBusy(true);
    setDialogError('');
    setError('');
    try {
      const data = await request('/api/admin/evaluation-types', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, ...(startMode === 'copy' ? { source_type: sourceType } : {}) }),
      });
      setTypeChoice(name);
      setDialog(null);
      const message = startMode === 'copy'
        ? `평가 종류를 추가하고 사용 중인 문항 ${data.copied_count}개를 복사했습니다.`
        : '평가 종류를 추가했습니다. 문항을 등록해 주세요.';
      await refreshAfterChange(message);
    } catch (failure) {
      setDialogError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  const saveQuestion = async (event) => {
    event.preventDefault();
    if (!form.category.trim() || !form.question_text.trim()) return setDialogError('문항 제목과 내용을 입력해 주세요.');
    setBusy(true);
    setDialogError('');
    setError('');
    try {
      await request(editingId === null ? '/api/admin/questions' : `/api/admin/questions/${editingId}`, {
        method: editingId === null ? 'POST' : 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      setTypeChoice(form.evaluation_type);
      setDialog(null);
      await refreshAfterChange(editingId === null ? '문항을 추가했습니다.' : '문항을 수정했습니다. 새 프로젝트부터 반영됩니다.');
    } catch (failure) {
      setDialogError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  const changeQuestionStatus = async (question) => {
    if (question.is_active && !window.confirm('이 문항을 삭제하시겠습니까? 프로젝트나 평가 기록에서 사용 중인 문항은 비활성화됩니다.')) return;
    setBusy(true);
    setError('');
    try {
      const data = await request(`/api/admin/questions/${question.id}${question.is_active ? '' : '/activate'}`,
        { method: question.is_active ? 'DELETE' : 'PATCH' });
      await refreshAfterChange(data.message);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteType = async () => {
    if (!window.confirm(`'${selectedType}' 평가 종류를 삭제하시겠습니까? 문항이나 프로젝트에서 사용 중이면 삭제할 수 없습니다.`)) return;
    setBusy(true);
    setError('');
    try {
      await request('/api/admin/evaluation-types', {
        method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: selectedType }),
      });
      setTypeChoice('');
      await refreshAfterChange('평가 종류를 삭제했습니다.');
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  const moveQuestion = async (index, direction) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= selectedQuestions.length) return;
    const ids = questions.map((question) => question.id);
    const first = ids.indexOf(selectedQuestions[index].id);
    const second = ids.indexOf(selectedQuestions[targetIndex].id);
    [ids[first], ids[second]] = [ids[second], ids[first]];
    setBusy(true);
    setError('');
    try {
      await request('/api/admin/questions/reorder', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_ids: ids }),
      });
      await refreshAfterChange('문항 순서를 변경했습니다. 새 프로젝트부터 반영됩니다.');
    } catch (failure) {
      await onRefresh();
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  };

  const setField = (key, value) => setForm((previous) => ({ ...previous, [key]: value }));
  const unavailable = busy || loading || Boolean(dataError);

  return (
    <section className="qm" aria-label="평가 문항 설정">
      <header className="qm-header">
        <div>
          <h2>평가 문항 설정</h2>
          <p>평가 종류별로 문항을 관리하세요.</p>
        </div>
        <button className="btn btn-primary qm-header-button" type="button" onClick={openTypeDialog} disabled={unavailable}>
          + 평가 종류 추가
        </button>
      </header>

      {dataError && <div className="qm-feedback qm-error" role="alert">{dataError} <button type="button" onClick={onRefresh}>다시 불러오기</button></div>}
      {error && <div className="qm-feedback qm-error" role="alert">{error}</div>}
      {notice && !dataError && <div className="qm-feedback qm-success" role="status">{notice}</div>}

      <div className="qm-layout">
        <aside className="qm-panel qm-types">
          <div className="qm-panel-heading"><h3>평가 종류</h3><span>{evaluationTypes.length}개</span></div>
          <div className="qm-type-list" aria-label="평가 종류 목록">
            {evaluationTypes.map((type) => {
              const count = questions.filter((question) => typeOf(question) === type && question.is_active).length;
              return <button key={type} type="button" className={`qm-type ${selectedType === type ? 'is-selected' : ''}`}
                aria-pressed={selectedType === type} disabled={unavailable} onClick={() => { setTypeChoice(type); setError(''); setNotice(''); }}>
                <span>{type}</span><small>사용 중 {count}</small>
              </button>;
            })}
            {!loading && !dataError && evaluationTypes.length === 0 && <p className="qm-empty-small">평가 종류를 추가해 주세요.</p>}
          </div>
        </aside>

        <div className="qm-panel qm-questions">
          {selectedType ? <>
            <div className="qm-questions-heading">
              <div><span className="qm-eyebrow">선택한 평가 종류</span><h3>{selectedType}</h3>
                <p>사용 중 {activeCount}개 · 전체 {selectedQuestions.length}개</p></div>
              <div className="qm-heading-actions">
                <button className="qm-text-button" type="button" onClick={deleteType} disabled={unavailable || selectedQuestions.length > 0}
                  title={selectedQuestions.length ? '등록된 문항이 있는 종류는 삭제할 수 없습니다.' : '사용 중인 프로젝트가 있으면 삭제할 수 없습니다.'}>종류 삭제</button>
                <button className="btn btn-primary qm-add-question" type="button" onClick={() => openQuestionDialog()} disabled={unavailable}>+ 문항 추가</button>
              </div>
            </div>
            <p className="qm-note">문항 변경은 새로 만드는 프로젝트부터 적용됩니다. 기존 프로젝트와 평가 기록은 유지됩니다.</p>
            {selectedQuestions.length === 0 ? <div className="qm-empty">
              <strong>아직 등록된 문항이 없습니다.</strong><p>문항을 추가한 뒤 이 평가 종류로 프로젝트를 만들 수 있습니다.</p>
              <button className="btn btn-secondary" type="button" onClick={() => openQuestionDialog()} disabled={unavailable}>첫 문항 추가</button>
            </div> : <ol className="qm-question-list">
              {selectedQuestions.map((question, index) => <li key={question.id} className={`qm-question ${question.is_active ? '' : 'is-inactive'}`}>
                <div className="qm-number">{String(index + 1).padStart(2, '0')}</div>
                <div className="qm-question-content">
                  <div className="qm-question-title"><strong>{question.category}</strong>
                    <span className="qm-badge">{question.is_essay ? '주관식' : '객관식'}</span>
                    <span className={`qm-badge ${question.is_active ? 'is-active' : 'is-muted'}`}>{question.is_active ? '사용 중' : '비활성'}</span>
                  </div>
                  <p className="qm-question-text">{question.question_text}</p>
                  {question.question_sub_text && <p className="qm-question-subtext">{question.question_sub_text}</p>}
                </div>
                <div className="qm-actions" aria-label={`${question.category} 문항 작업`}>
                  <div className="qm-order-buttons">
                    <button type="button" aria-label={`${question.category} 위로 이동`} onClick={() => moveQuestion(index, -1)} disabled={unavailable || index === 0}>↑</button>
                    <button type="button" aria-label={`${question.category} 아래로 이동`} onClick={() => moveQuestion(index, 1)} disabled={unavailable || index === selectedQuestions.length - 1}>↓</button>
                  </div>
                  <button type="button" onClick={() => openQuestionDialog(question)} disabled={unavailable}>수정</button>
                  <button type="button" className={question.is_active ? 'qm-danger' : ''} onClick={() => changeQuestionStatus(question)} disabled={unavailable}>
                    {question.is_active ? '삭제' : '복구'}
                  </button>
                </div>
              </li>)}
            </ol>}
          </> : <div className="qm-empty"><strong>평가 종류를 먼저 추가해 주세요.</strong></div>}
        </div>
      </div>

      {dialog && <div className="qm-modal-backdrop" onKeyDown={(event) => { if (event.key === 'Escape') closeDialog(); }}>
        <div className="qm-modal" role="dialog" aria-modal="true" aria-labelledby="qm-dialog-title">
          <div className="qm-modal-heading">
            <div><span className="qm-eyebrow">평가 문항 설정</span><h3 id="qm-dialog-title">{dialog === 'type' ? '평가 종류 추가' : editingId === null ? '문항 추가' : '문항 수정'}</h3></div>
            <button type="button" className="qm-close" aria-label="닫기" onClick={closeDialog} disabled={busy}>×</button>
          </div>
          {dialogError && <div className="qm-feedback qm-error" role="alert">{dialogError}</div>}
          {dialog === 'type' ? <form className="qm-form" onSubmit={createType}>
            <label htmlFor="qm-type-name">평가 종류 이름</label>
            <input id="qm-type-name" className="input-field" value={typeName} onChange={(event) => setTypeName(event.target.value)}
              placeholder="예: 정규직 전환평가" autoFocus required />
            <fieldset className="qm-start-options"><legend>문항 시작 방법</legend>
              <label><input type="radio" name="qm-start" value="empty" checked={startMode === 'empty'} onChange={() => setStartMode('empty')} /> 빈 문항으로 시작</label>
              <label><input type="radio" name="qm-start" value="copy" checked={startMode === 'copy'} onChange={() => setStartMode('copy')} disabled={!evaluationTypes.length} /> 기존 종류의 문항 복사</label>
            </fieldset>
            {startMode === 'copy' && <>
              <label htmlFor="qm-source-type">복사할 평가 종류</label>
              <select id="qm-source-type" className="input-field" value={sourceType} onChange={(event) => setSourceType(event.target.value)} required>
                <option value="">선택해 주세요</option>{evaluationTypes.map((type) => <option key={type} value={type}>{type}</option>)}
              </select>
              <p className="qm-form-hint">사용 중인 문항만 별도로 복사합니다. 복사본을 바꿔도 원본은 유지됩니다.</p>
            </>}
            <div className="qm-modal-actions"><button type="button" className="btn btn-secondary" onClick={closeDialog} disabled={busy}>취소</button>
              <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? '추가 중...' : '종류 추가'}</button></div>
          </form> : <form className="qm-form" onSubmit={saveQuestion}>
            <label htmlFor="qm-question-type">평가 종류</label>
            <select id="qm-question-type" className="input-field" value={form.evaluation_type} onChange={(event) => setField('evaluation_type', event.target.value)} required>
              {evaluationTypes.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
            <label htmlFor="qm-question-title">문항 제목</label>
            <input id="qm-question-title" className="input-field" value={form.category} onChange={(event) => setField('category', event.target.value)}
              placeholder="예: 협업 능력" autoFocus required />
            <label htmlFor="qm-answer-type">문항 종류</label>
            <select id="qm-answer-type" className="input-field" value={form.is_essay} onChange={(event) => setField('is_essay', Number(event.target.value))}>
              <option value={0}>객관식 (6~10점)</option><option value={1}>주관식 (서술형)</option>
            </select>
            <label htmlFor="qm-question-text">문항 내용</label>
            <textarea id="qm-question-text" className="input-field" rows="3" value={form.question_text}
              onChange={(event) => setField('question_text', event.target.value)} placeholder="평가자가 답변할 내용을 입력하세요." required />
            <label htmlFor="qm-question-subtext">보조 설명 <span>선택</span></label>
            <textarea id="qm-question-subtext" className="input-field" rows="2" value={form.question_sub_text}
              onChange={(event) => setField('question_sub_text', event.target.value)} placeholder="필요한 경우 참고 설명을 입력하세요." />
            <p className="qm-form-hint">문항 변경은 새 프로젝트부터 반영됩니다.</p>
            <div className="qm-modal-actions"><button type="button" className="btn btn-secondary" onClick={closeDialog} disabled={busy}>취소</button>
              <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? '저장 중...' : '저장'}</button></div>
          </form>}
        </div>
      </div>}
    </section>
  );
}

export default QuestionManager;
