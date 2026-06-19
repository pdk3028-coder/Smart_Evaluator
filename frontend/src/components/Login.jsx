import React, { useState } from 'react';

function Login({ onLoginSuccess }) {
  const [activeTab, setActiveTab] = useState('user'); // user, admin
  const [empId, setEmpId] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setLoading(true);

    const loginId = activeTab === 'user' ? empId.trim() : 'ADMIN';
    const loginPw = activeTab === 'admin' ? password : null;

    if (activeTab === 'user' && !loginId) {
      setErrorMsg('사원번호를 입력해 주세요.');
      setLoading(false);
      return;
    }
    if (activeTab === 'user' && !agreePrivacy) {
      setErrorMsg('개인정보 수집 및 이용 동의에 체크해 주세요.');
      setLoading(false);
      return;
    }
    if (activeTab === 'admin' && !password) {
      setErrorMsg('관리자 비밀번호를 입력해 주세요.');
      setLoading(false);
      return;
    }

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          emp_id: loginId,
          password: loginPw,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || '로그인에 실패했습니다.');
      }

      // 로그인 성공 시 콜백 호출
      onLoginSuccess(data);
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-content" style={{ justifyContent: 'center', minHeight: '80vh' }}>
      <div style={{ textAlign: 'center', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: '700', color: 'var(--primary-color)', marginBottom: '8px' }}>
          풍산 스마트 평가 시스템
        </h2>
      </div>

      <div className="card" style={{ padding: '24px' }}>
        {/* 로그인 탭 메뉴 */}
        <div className="tab-container" style={{ margin: '-24px -24px 24px -24px', borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}>
          <div
            className={`tab-item ${activeTab === 'user' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('user');
              setErrorMsg('');
              setAgreePrivacy(false);
            }}
          >
            임직원 로그인
          </div>
          <div
            className={`tab-item ${activeTab === 'admin' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('admin');
              setErrorMsg('');
              setAgreePrivacy(false);
            }}
          >
            관리자 로그인
          </div>
        </div>

        {errorMsg && (
          <div className="alert alert-error" style={{ marginBottom: '16px' }}>
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {activeTab === 'user' ? (
            <>
              <div className="input-group">
                <label className="input-label" htmlFor="empId">사원번호</label>
                <input
                  id="empId"
                  className="input-field"
                  type="text"
                  placeholder="사번을 입력하세요 (예: 0151004)"
                  value={empId}
                  onChange={(e) => setEmpId(e.target.value)}
                  disabled={loading}
                />
              </div>

              {/* 개인정보 수집 및 이용 동의 */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
                <div style={{
                  fontSize: '11px',
                  color: 'var(--text-secondary)',
                  backgroundColor: '#f8fafc',
                  padding: '12px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  maxHeight: '100px',
                  overflowY: 'auto',
                  lineHeight: '1.5',
                  textAlign: 'left'
                }}>
                  <strong>[개인정보 수집 및 이용 동의]</strong><br />
                  1. 수집목적: 동료평가 운영, 피평가자 검증 및 서명 본인 인증<br />
                  2. 수집항목: 사번, 성명, 소속 부서, 직급, 연락처, 평가 답변 내역, 서명 이미지 데이터<br />
                  3. 보유기간: 해당 평가 프로젝트 목적 달성 시(또는 퇴사 시) 즉시 파기<br />
                  * 귀하는 동의를 거부할 권리가 있으나, 거부 시 본 평가 시스템 이용 및 로그인에 제한이 따를 수 있습니다.
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', userSelect: 'none' }}>
                  <input
                    type="checkbox"
                    checked={agreePrivacy}
                    onChange={(e) => setAgreePrivacy(e.target.checked)}
                    disabled={loading}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <span>개인정보 수집 및 이용에 동의합니다 (필수)</span>
                </label>
              </div>
            </>
          ) : (
            <>
              <div className="input-group">
                <label className="input-label">관리자 사번</label>
                <input
                  className="input-field"
                  type="text"
                  value="ADMIN"
                  disabled
                />
              </div>
              <div className="input-group">
                <label className="input-label" htmlFor="adminPw">비밀번호</label>
                <input
                  id="adminPw"
                  className="input-field"
                  type="password"
                  placeholder="관리자 비밀번호를 입력하세요"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                />
              </div>
            </>
          )}

          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? '로그인 중...' : '로그인'}
          </button>
        </form>
      </div>

      <div style={{ textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)', marginTop: '16px' }}>
        문의 : 인사담당 박동규 대리 (052-231-9134)
      </div>
    </div>
  );
}

export default Login;
