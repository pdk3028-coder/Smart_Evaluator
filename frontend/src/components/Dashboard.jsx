import React, { useState, useEffect } from 'react';

function Dashboard({ user, onSelectAssignment, onLogout }) {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchAssignments = async () => {
    try {
      const response = await fetch(`/api/evaluations/assignments?evaluator_id=${user.id}`);
      if (!response.ok) {
        throw new Error('평가 배정 목록을 불러오지 못했습니다.');
      }
      const data = await response.json();
      setAssignments(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssignments();
  }, [user.id]);

  // 완료 개수 및 진행률 계산
  const totalCount = assignments.length;
  const completedCount = assignments.filter((a) => a.status === 'completed').count || assignments.filter((a) => a.status === 'completed').length;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <>
      {/* 헤더 바 */}
      <div className="header-bar">
        <span className="header-title">동료사원평가</span>
        <button className="header-btn" onClick={onLogout}>로그아웃</button>
      </div>

      <div className="page-content">
        {/* 사용자 환영 카드 */}
        <div className="card" style={{ backgroundColor: 'var(--primary-color)', color: '#ffffff', border: 'none' }}>
          <p style={{ fontSize: '14px', opacity: 0.9, marginBottom: '4px' }}>반갑습니다</p>
          <h3 style={{ fontSize: '20px', fontWeight: '700' }}>
            {user.emp_name} 님
          </h3>
          <p style={{ fontSize: '13px', opacity: 0.8, marginTop: '8px' }}>
            사번: {user.emp_id}
          </p>
        </div>

        {/* 진행률 영역 */}
        {totalCount > 0 && (
          <div className="card" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '14px', fontWeight: '600' }}>
              <span style={{ color: 'var(--text-secondary)' }}>평가 진행 현황</span>
              <span style={{ color: 'var(--primary-color)' }}>
                {completedCount} / {totalCount}명 완료 ({progressPercent}%)
              </span>
            </div>
            <div className="progress-container">
              <div className="progress-bar" style={{ width: `${progressPercent}%` }}></div>
            </div>
          </div>
        )}

        {/* 평가 리스트 목록 */}
        <div style={{ marginTop: '8px' }}>
          <h4 style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            평가 대상 동료 목록
          </h4>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
              평가 대상을 불러오는 중입니다...
            </div>
          ) : error ? (
            <div className="alert alert-error">
              <span>{error}</span>
            </div>
          ) : assignments.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-secondary)' }}>
              <p style={{ fontSize: '15px', fontWeight: '500', marginBottom: '4px' }}>배정된 평가 대상자가 없습니다.</p>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>관리자가 배정을 완료할 때까지 잠시 대기해 주세요.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {assignments.map((item) => {
                const isCompleted = item.status === 'completed';
                return (
                  <div
                    key={item.assignment_id}
                    className={`card ${!isCompleted ? 'card-interactive' : ''}`}
                    style={{
                      borderLeft: isCompleted
                        ? '4px solid var(--success)'
                        : item.status === 'saved'
                        ? '4px solid var(--warning)'
                        : '4px solid var(--primary-color)',
                      backgroundColor: isCompleted ? '#f8fafc' : 'var(--surface-color)',
                      opacity: isCompleted ? 0.85 : 1,
                      cursor: isCompleted ? 'default' : 'pointer'
                    }}
                    onClick={() => {
                      if (!isCompleted) {
                        onSelectAssignment(item);
                      }
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ paddingRight: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '6px' }}>
                          <span style={{ fontSize: '18px', fontWeight: '700', color: 'var(--text-primary)' }}>
                            {item.project_title || `${item.name} 사원 동료평가`}
                          </span>
                        </div>
                        <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                          대상자: {item.name} {item.position || ''} | 소속: {item.team_name || '소속 없음'} | 사번: {item.emp_id}
                        </p>
                      </div>

                      {/* 상태 뱃지 */}
                      <div style={{ flexShrink: 0 }}>
                        {isCompleted ? (
                          <span style={{
                            padding: '6px 10px',
                            borderRadius: '20px',
                            backgroundColor: '#d1fae5',
                            color: '#065f46',
                            fontSize: '12px',
                            fontWeight: '600',
                            whiteSpace: 'nowrap'
                          }}>
                            제출 완료
                          </span>
                        ) : item.status === 'saved' ? (
                          <span style={{
                            padding: '6px 10px',
                            borderRadius: '20px',
                            backgroundColor: '#fef3c7',
                            color: '#d97706',
                            fontSize: '12px',
                            fontWeight: '600',
                            whiteSpace: 'nowrap'
                          }}>
                            임시 저장
                          </span>
                        ) : (
                          <span style={{
                            padding: '6px 10px',
                            borderRadius: '20px',
                            backgroundColor: '#eff6ff',
                            color: 'var(--primary-color)',
                            fontSize: '12px',
                            fontWeight: '600',
                            whiteSpace: 'nowrap'
                          }}>
                            평가 대기
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default Dashboard;
