import React, { useState, useEffect } from 'react';

function EvaluationForm({ user, assignment, onBack, onSubmitSuccess }) {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({}); // { question_id: { score: int, answer_text: str } }
  const [loading, setLoading] = useState(true);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertModalMsg, setAlertModalMsg] = useState('');
  
  const [showSignatureModal, setShowSignatureModal] = useState(false);
  const canvasRef = React.useRef(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);

  // 질문 목록 및 기존 임시저장 답변 가져오기
  const fetchQuestionsAndDraft = async () => {
    try {
      const [qRes, draftRes] = await Promise.all([
        fetch(`/api/evaluations/questions?assignment_id=${assignment.assignment_id}`),
        fetch(`/api/evaluations/draft?assignment_id=${assignment.assignment_id}`)
      ]);

      if (!qRes.ok || !draftRes.ok) {
        throw new Error('평가 정보를 불러오지 못했습니다.');
      }

      const qData = await qRes.json();
      const draftData = await draftRes.json();

      setQuestions(qData);

      // 기본 답변 구조 생성
      const initialAnswers = {};
      qData.forEach((q) => {
        initialAnswers[q.id] = {
          question_id: q.id,
          score: null, // 초기에는 선택되지 않은 상태로 설정
          answer_text: '',
        };
      });

      // 기존 임시저장(draft)이 있다면 덮어쓰기
      if (draftData.has_draft && draftData.answers.length > 0) {
        draftData.answers.forEach((ans) => {
          if (initialAnswers[ans.question_id]) {
            initialAnswers[ans.question_id] = {
              question_id: ans.question_id,
              score: ans.score,
              answer_text: ans.answer_text || '',
            };
          }
        });
      }

      setAnswers(initialAnswers);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuestionsAndDraft();
  }, []);

  // 임시 저장 처리
  const handleSaveDraft = async () => {
    setErrorMsg('');
    setSubmitLoading(true);

    const submitPayload = {
      assignment_id: assignment.assignment_id,
      evaluator_id: user.id,
      evaluatee_id: assignment.employee_id,
      answers: Object.values(answers).map((ans) => ({
        question_id: ans.question_id,
        score: ans.score,
        answer_text: ans.answer_text,
      })),
    };

    try {
      const response = await fetch('/api/evaluations/draft', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(submitPayload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '임시 저장에 실패했습니다.');
      }

      alert('평가 내용이 임시 저장되었습니다.\n최종 제출 전까지는 언제든 수정하실 수 있습니다.');
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSubmitLoading(false);
    }
  };

  // 객관식 점수 핸들러
  const handleScoreChange = (qId, scoreVal) => {
    setAnswers((prev) => ({
      ...prev,
      [qId]: {
        ...prev[qId],
        score: parseInt(scoreVal, 10),
      },
    }));
  };

  // 주관식 텍스트 핸들러
  const handleTextChange = (qId, textVal) => {
    setAnswers((prev) => ({
      ...prev,
      [qId]: {
        ...prev[qId],
        answer_text: textVal,
      },
    }));
  };

  // Canvas 드로잉 초기 설정
  useEffect(() => {
    if (showSignatureModal && canvasRef.current) {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      canvas.width = 400;
      canvas.height = 200;
      ctx.strokeStyle = '#0f172a'; // 선 색상 (slate-900)
      ctx.lineWidth = 3.5;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      
      // 배경 흰색으로 기본 채우기
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
  }, [showSignatureModal]);

  // 그리기 함수들
  const startDrawing = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    
    ctx.beginPath();
    ctx.moveTo(clientX - rect.left, clientY - rect.top);
    setIsDrawing(true);
  };

  const draw = (e) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    
    ctx.lineTo(clientX - rect.left, clientY - rect.top);
    ctx.stroke();
    setHasSignature(true);
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 배경 흰색 리셋
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    setHasSignature(false);
  };

  // 폼 제출 유효성 검사 후 서명 모달 띄우기
  const handleOpenSignatureModal = (e) => {
    e.preventDefault();
    setErrorMsg('');
    
    // 유효성 검사 (객관식 선택 및 주관식 답변 필수 여부)
    let isValid = true;
    for (const q of questions) {
      if (!q.is_essay && (answers[q.id]?.score === null || answers[q.id]?.score === undefined)) {
        setAlertModalMsg('모든 객관식 평가 문항을 평가해 주세요.');
        setShowAlertModal(true);
        isValid = false;
        break;
      }
      if (q.is_essay && (!answers[q.id]?.answer_text || !answers[q.id].answer_text.trim())) {
        setAlertModalMsg('모든 주관식 의견란을 입력해 주세요.');
        setShowAlertModal(true);
        isValid = false;
        break;
      }
    }

    if (!isValid) {
      return;
    }

    setShowSignatureModal(true);
    setHasSignature(false); // 열 때마다 초기 서명 상태 false로
  };

  // 최종 제출 (서명 데이터 포함)
  const handleSubmitFinal = async () => {
    if (!hasSignature) {
      alert('서명을 작성해 주세요.');
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    const signatureDataUrl = canvas.toDataURL('image/png');

    setErrorMsg('');
    setSubmitLoading(true);
    setShowSignatureModal(false);

    const submitPayload = {
      assignment_id: assignment.assignment_id,
      evaluator_id: user.id,
      evaluatee_id: assignment.employee_id,
      signature_data: signatureDataUrl,
      answers: Object.values(answers).map((ans) => ({
        question_id: ans.question_id,
        score: ans.score,
        answer_text: ans.answer_text,
      })),
    };

    try {
      const response = await fetch('/api/evaluations/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(submitPayload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '평가 제출에 실패했습니다.');
      }

      alert('평가가 디지털 서명과 함께 최종 제출되었습니다.\n제출 완료 후에는 더 이상 수정 및 재입력이 불가능합니다.');
      onSubmitSuccess();
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSubmitLoading(false);
    }
  };

  return (
    <>
      {/* 헤더 바 */}
      <div className="header-bar">
        <button className="header-btn" onClick={onBack}>← 뒤로</button>
        <span className="header-title" style={{ fontSize: '16px' }}>{assignment.project_title || "동료 평가 작성"}</span>
        <div style={{ width: '40px' }}></div> {/* 균형 맞춤 */}
      </div>

      <div className="page-content">
        {/* 피평가 사원 정보 요약 */}
        <div className="card" style={{ borderLeft: '4px solid var(--primary-color)' }}>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>평가 대상 동료</p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
            <span style={{ fontSize: '20px', fontWeight: '700' }}>{assignment.name}</span>
            <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>{assignment.position}</span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            소속: {assignment.team_name} | 사번: {assignment.emp_id}
          </p>
        </div>

        {errorMsg && (
          <div className="alert alert-error">
            <span>{errorMsg}</span>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
            평가 문항 로딩 중...
          </div>
        ) : error ? (
          <div className="alert alert-error">
            <span>{error}</span>
          </div>
        ) : (
          <form onSubmit={handleOpenSignatureModal} style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '30px' }}>
            {questions.map((q, qIndex) => (
              <div className="card" key={q.id}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      backgroundColor: 'var(--primary-light)',
                      color: 'var(--primary-color)',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontSize: '13px',
                      fontWeight: '700',
                      height: 'fit-content'
                    }}>
                      Q{qIndex + 1}
                    </span>
                    <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--primary-color)' }}>
                      [{q.category}]
                    </span>
                  </div>
                  <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', lineHeight: '1.5', whiteSpace: 'pre-wrap', paddingLeft: '4px' }}>
                    {q.question_text}
                  </div>
                  {q.question_sub_text && (
                    <div style={{
                      fontSize: '12px',
                      color: '#64748b',
                      lineHeight: '1.5',
                      whiteSpace: 'pre-wrap',
                      paddingLeft: '4px',
                      marginTop: '6px'
                    }}>
                      {q.question_sub_text}
                    </div>
                  )}
                </div>

                {/* 객관식 (5점 척도 - 6~10점 선택) */}
                {!q.is_essay ? (
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '12px', padding: '0 8px' }}>
                    {[6, 7, 8, 9, 10].map((score) => {
                      const isSelected = answers[q.id]?.score === score;
                      return (
                        <button
                          key={score}
                          type="button"
                          onClick={() => handleScoreChange(q.id, score)}
                          style={{
                            width: '44px',
                            height: '44px',
                            borderRadius: '50%',
                            border: isSelected ? '2px solid var(--primary-color)' : '1px solid var(--border-color)',
                            backgroundColor: isSelected ? 'var(--primary-light)' : 'var(--surface-color)',
                            color: isSelected ? 'var(--primary-color)' : 'var(--text-secondary)',
                            fontWeight: '700',
                            fontSize: '16px',
                            cursor: 'pointer',
                            transition: 'var(--transition-fast)'
                          }}
                        >
                          {score}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  /* 주관식 서술형 */
                  <div className="input-group">
                    <textarea
                      className="input-field"
                      rows="4"
                      placeholder="구체적인 사례와 행동을 바탕으로 피드백을 작성해 주세요. 작성한 내용은 익명으로 처리됩니다."
                      style={{ resize: 'none', fontSize: '14px', lineHeight: '1.5' }}
                      value={answers[q.id]?.answer_text || ''}
                      onChange={(e) => handleTextChange(q.id, e.target.value)}
                      disabled={submitLoading}
                      maxLength={1000}
                    />
                    <div style={{ textAlign: 'right', fontSize: '11px', color: 'var(--text-muted)' }}>
                      {(answers[q.id]?.answer_text || '').length} / 1000 자
                    </div>
                  </div>
                )}
              </div>
            ))}

            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
              <button
                className="btn btn-secondary"
                type="button"
                onClick={handleSaveDraft}
                disabled={submitLoading}
                style={{ flex: 1, padding: '12px', fontSize: '14px', fontWeight: '700' }}
              >
                임시 저장
              </button>
              <button
                className="btn btn-primary"
                type="submit"
                disabled={submitLoading}
                style={{ flex: 2, padding: '12px', fontSize: '14px', fontWeight: '700' }}
              >
                {submitLoading ? '제출 중...' : '최종 제출 (수정 불가)'}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* 서명 모달 팝업 */}
      {showSignatureModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.6)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000,
          backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            backgroundColor: 'var(--surface-color)',
            padding: '24px',
            borderRadius: '16px',
            width: '90%',
            maxWidth: '440px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.05)',
            border: '1px solid var(--border-color)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ textAlign: 'center' }}>
              <h3 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '6px' }}>최종 제출 서명</h3>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                평가 내용을 최종 제출하시려면 서명란에 서명해 주세요.<br />
                제출 완료 후에는 수정이 불가능합니다.
              </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <canvas
                ref={canvasRef}
                style={{
                  border: '1px dashed #cbd5e1',
                  borderRadius: '8px',
                  cursor: 'crosshair',
                  backgroundColor: '#ffffff',
                  touchAction: 'none'
                }}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
              />
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={clearCanvas}
                style={{ flex: 1, padding: '10px', fontSize: '13px', fontWeight: '600' }}
              >
                초기화
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowSignatureModal(false)}
                style={{ flex: 1, padding: '10px', fontSize: '13px', fontWeight: '600', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}
              >
                취소
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleSubmitFinal}
                disabled={submitLoading}
                style={{ flex: 2, padding: '10px', fontSize: '13px', fontWeight: '700' }}
              >
                서명 완료 및 제출
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 경고 알림 모달 팝업 */}
      {showAlertModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.6)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1100,
          backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            backgroundColor: 'var(--surface-color)',
            padding: '24px',
            borderRadius: '16px',
            width: '85%',
            maxWidth: '380px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.15), 0 10px 10px -5px rgba(0, 0, 0, 0.05)',
            border: '1px solid var(--border-color)',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                backgroundColor: '#fee2e2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 12px auto'
              }}>
                <span style={{ color: '#ef4444', fontSize: '24px', fontWeight: '800' }}>!</span>
              </div>
              <h3 style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px' }}>
                평가 항목 누락
              </h3>
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                {alertModalMsg}
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowAlertModal(false)}
              style={{ padding: '10px', fontSize: '14px', fontWeight: '700' }}
            >
              확인
            </button>
          </div>
        </div>
      )}
    </>
  );
}

export default EvaluationForm;
