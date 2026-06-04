import React, { useState } from 'react';

function Login({ onLoginSuccess }) {
  const [activeTab, setActiveTab] = useState('user'); // user, admin
  const [empId, setEmpId] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

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
            }}
          >
            임직원 로그인
          </div>
          <div
            className={`tab-item ${activeTab === 'admin' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('admin');
              setErrorMsg('');
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
