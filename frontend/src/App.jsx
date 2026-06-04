import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import EvaluationForm from './components/EvaluationForm';
import AdminDashboard from './components/AdminDashboard';

function App() {
  const [user, setUser] = useState(null);
  const [screen, setScreen] = useState('login'); // login, dashboard, evaluation, admin
  const [selectedAssignment, setSelectedAssignment] = useState(null);

  // 로컬 스토리지에서 세션 복원 시도
  useEffect(() => {
    const savedUser = localStorage.getItem('evaluator_user');
    if (savedUser) {
      const parsedUser = JSON.parse(savedUser);
      setUser(parsedUser);
      if (parsedUser.is_admin) {
        setScreen('admin');
      } else {
        setScreen('dashboard');
      }
    }
  }, []);

  // 관리자 모드 시 데스크탑 와이드 레이아웃 전환
  useEffect(() => {
    const rootEl = document.getElementById('root');
    if (rootEl) {
      if (screen === 'admin') {
        rootEl.style.maxWidth = '1200px';
        rootEl.style.height = '100vh';
        rootEl.style.maxHeight = 'none';
        rootEl.style.borderRadius = '0';
      } else {
        rootEl.style.maxWidth = '';
        rootEl.style.height = '';
        rootEl.style.maxHeight = '';
        rootEl.style.borderRadius = '';
      }
    }
  }, [screen]);

  const handleLoginSuccess = (loginData) => {
    setUser(loginData);
    localStorage.setItem('evaluator_user', JSON.stringify(loginData));
    if (loginData.is_admin) {
      setScreen('admin');
    } else {
      setScreen('dashboard');
    }
  };

  const handleLogout = () => {
    setUser(null);
    setSelectedAssignment(null);
    setScreen('login');
    localStorage.removeItem('evaluator_user');
  };

  const handleSelectAssignment = (assignment) => {
    setSelectedAssignment(assignment);
    setScreen('evaluation');
  };

  const handleEvaluationSubmit = () => {
    setSelectedAssignment(null);
    setScreen('dashboard');
  };

  return (
    <>
      {screen === 'login' && (
        <Login onLoginSuccess={handleLoginSuccess} />
      )}

      {screen === 'dashboard' && user && (
        <Dashboard
          user={user}
          onSelectAssignment={handleSelectAssignment}
          onLogout={handleLogout}
        />
      )}

      {screen === 'evaluation' && user && selectedAssignment && (
        <EvaluationForm
          user={user}
          assignment={selectedAssignment}
          onBack={() => setScreen('dashboard')}
          onSubmitSuccess={handleEvaluationSubmit}
        />
      )}

      {screen === 'admin' && user && user.is_admin && (
        <AdminDashboard onLogout={handleLogout} />
      )}
    </>
  );
}

export default App;
