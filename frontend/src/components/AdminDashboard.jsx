import React, { useState, useEffect } from 'react';
import { jsPDF } from 'jspdf';
import html2canvas from 'html2canvas';
import { PDFDocument } from 'pdf-lib';

function AdminDashboard({ onLogout }) {
  const [employees, setEmployees] = useState([]);
  const [projects, setProjects] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [lastUploadTime, setLastUploadTime] = useState('로딩 중...');
  
  // 아코디언 개폐 및 필터용 상태값 추가
  const [expandedProjectIds, setExpandedProjectIds] = useState([]);
  const [projectSearchText, setProjectSearchText] = useState('');
  const [projectStatusFilter, setProjectStatusFilter] = useState('all');

  // 관리자 탭 전환 상태 ('employees': 사원명부 관리, 'projects': 프로젝트 관리, 'questions': 문항 관리)
  const [activeTab, setActiveTab] = useState('projects');

  // 신규 실시간 필터 및 자동완성 검색용 상태값들 추가
  const [employeeSearchText, setEmployeeSearchText] = useState('');
  const [projectSearchTextForAssignment, setProjectSearchTextForAssignment] = useState('');
  const [showProjectDropdownForAssignment, setShowProjectDropdownForAssignment] = useState(false);
  const [activeProjectIndexForAssignment, setActiveProjectIndexForAssignment] = useState(0);

  // 평가 문항 관리 상태들
  const [questions, setQuestions] = useState([]);
  const [questionText, setQuestionText] = useState('');
  const [questionSubText, setQuestionSubText] = useState('');
  const [questionCategory, setQuestionCategory] = useState('');
  const [questionIsEssay, setQuestionIsEssay] = useState(0); // 0: 객관식, 1: 주관식
  const [editingQuestionId, setEditingQuestionId] = useState(null);
  const [editQuestionText, setEditQuestionText] = useState('');
  const [editQuestionSubText, setEditQuestionSubText] = useState('');
  const [editQuestionCategory, setEditQuestionCategory] = useState('');
  const [editQuestionIsEssay, setEditQuestionIsEssay] = useState(0);

  // 투 트랙 배정 방식 선택 ('search': 직접 검색, 'excel': 엑셀 일괄 추가)
  const [activeTrack, setActiveTrack] = useState('search');

  // 피평가자 검색 관련 상태
  const [projectEvaluateeId, setProjectEvaluateeId] = useState('');
  const [evaluateeSearchText, setEvaluateeSearchText] = useState('');
  const [showEvaluateeDropdown, setShowEvaluateeDropdown] = useState(false);
  const [activeEvaluateeIndex, setActiveEvaluateeIndex] = useState(0);

  // 평가자 직접 검색 관련 상태
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [evaluatorSearchText, setEvaluatorSearchText] = useState('');
  const [showEvaluatorDropdown, setShowEvaluatorDropdown] = useState(false);
  const [selectedEvaluators, setSelectedEvaluators] = useState([]); 
  const [activeEvaluatorIndex, setActiveEvaluatorIndex] = useState(0);

  // 엑셀 붙여넣기 일괄 추가 상태
  const [excelPasteText, setExcelPasteText] = useState('');
  const [mappingPreview, setMappingPreview] = useState([]); // [{ inputName, matchedEmp, status, candidates }]

  const [file, setFile] = useState(null);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadError, setUploadError] = useState('');

  // 직접 사원 추가 입력 상태
  const [newEmpId, setNewEmpId] = useState('');
  const [newEmpName, setNewEmpName] = useState('');
  const [newEmpTeam, setNewEmpTeam] = useState('');
  const [newEmpPosition, setNewEmpPosition] = useState('');
  const [newEmpPhone, setNewEmpPhone] = useState('');
  const [empCreateError, setEmpCreateError] = useState('');
  const [empCreateSuccess, setEmpCreateSuccess] = useState('');

  
  const [projCreateError, setProjCreateError] = useState('');
  const [projCreateSuccess, setProjCreateSuccess] = useState('');
  const [assignmentError, setAssignmentError] = useState('');
  const [assignmentSuccess, setAssignmentSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfLoadingMsg, setPdfLoadingMsg] = useState('');

  // 평가 기간 상태 (기본값: 시작일은 오늘, 종료일은 일주일 뒤)
  const getTodayStr = () => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const getWeekLaterStr = () => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const [startDate, setStartDate] = useState(getTodayStr());
  const [endDate, setEndDate] = useState(getWeekLaterStr());
  const [evaluationType, setEvaluationType] = useState('동료사원 평가');

  // 평가 문항 추가 상태
  const [questionEvaluationType, setQuestionEvaluationType] = useState('동료사원 평가');
  const [editQuestionEvaluationType, setEditQuestionEvaluationType] = useState('동료사원 평가');
  const [questionFilterType, setQuestionFilterType] = useState('전체');

  // 동적 평가 종류 상태
  const [evaluationTypes, setEvaluationTypes] = useState(['동료사원 평가', '직무능력 평가', '다면평가']);
  const [newEvalTypeName, setNewEvalTypeName] = useState('');
  const [evalTypeSuccess, setEvalTypeSuccess] = useState('');
  const [evalTypeError, setEvalTypeError] = useState('');

  // 인라인 기간 수정 관련 상태 및 함수
  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editStartDate, setEditStartDate] = useState('');
  const [editEndDate, setEditEndDate] = useState('');

  const handleStartEditPeriod = (proj) => {
    setEditingProjectId(proj.project_id);
    setEditStartDate(proj.start_date || getTodayStr());
    setEditEndDate(proj.end_date || getWeekLaterStr());
  };

  const handleCancelEditPeriod = () => {
    setEditingProjectId(null);
    setEditStartDate('');
    setEditEndDate('');
  };

  const handleSavePeriod = async (projId) => {
    if (!editStartDate || !editEndDate) {
      alert('시작일과 종료일을 모두 입력해 주세요.');
      return;
    }

    try {
      const response = await fetch(`/api/admin/projects/${projId}/period`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          start_date: editStartDate,
          end_date: editEndDate
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '평가 기간 수정에 실패했습니다.');
      }

      alert(data.message);
      setEditingProjectId(null);
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 아코디언 열기/닫기 토글 함수
  const toggleProjectExpand = (projId) => {
    setExpandedProjectIds((prev) =>
      prev.includes(projId)
        ? prev.filter((id) => id !== projId)
        : [...prev, projId]
    );
  };

  // 프로젝트 필터링용 날짜 계산 유틸
  const getTodayDateOnly = () => {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  // 실시간 검색 및 상태 필터 파이프라인
  const filteredProjects = projects.filter((proj) => {
    const query = projectSearchText.toLowerCase().trim();
    const matchesSearch = query === '' || 
      proj.title.toLowerCase().includes(query) ||
      proj.evaluatee_name.toLowerCase().includes(query) ||
      (proj.evaluatee_team && proj.evaluatee_team.toLowerCase().includes(query)) ||
      (proj.evaluatee_position && proj.evaluatee_position.toLowerCase().includes(query)) ||
      proj.evaluatee_emp_id.toLowerCase().includes(query);

    if (!matchesSearch) return false;

    if (projectStatusFilter === 'all') return true;
    
    const todayStr = getTodayDateOnly();
    if (proj.start_date && proj.end_date) {
      if (projectStatusFilter === 'pending') {
        return todayStr < proj.start_date;
      } else if (projectStatusFilter === 'expired') {
        return todayStr > proj.end_date;
      } else if (projectStatusFilter === 'active') {
        return todayStr >= proj.start_date && todayStr <= proj.end_date;
      }
    } else {
      return projectStatusFilter === 'active';
    }
    return true;
  });

  // 배정 설정 카드에서 검색어에 따라 필터링되는 프로젝트 리스트
  const filteredProjectsForSelection = projects.filter((proj) => {
    const query = projectSearchTextForAssignment.toLowerCase().trim();
    if (query === '') return true;
    return (
      proj.title.toLowerCase().includes(query) ||
      proj.evaluatee_name.toLowerCase().includes(query) ||
      (proj.evaluatee_team && proj.evaluatee_team.toLowerCase().includes(query)) ||
      (proj.evaluatee_position && proj.evaluatee_position.toLowerCase().includes(query)) ||
      proj.evaluatee_emp_id.toLowerCase().includes(query)
    );
  });


  // 사원 목록, 프로젝트 목록, 배정 현황 및 업로드 시각 가져오기
  const fetchData = async () => {
    try {
      const [empRes, projRes, assignRes, timeRes, qRes, typeRes] = await Promise.all([
        fetch('/api/admin/employees'),
        fetch('/api/admin/projects'),
        fetch('/api/admin/assignments'),
        fetch('/api/admin/last-upload-time'),
        fetch('/api/admin/questions'),
        fetch('/api/evaluation-types')
      ]);

      if (!empRes.ok || !projRes.ok || !assignRes.ok || !timeRes.ok || !qRes.ok || !typeRes.ok) {
        throw new Error('데이터를 가져오는데 실패했습니다.');
      }

      const empData = await empRes.json();
      const projData = await projRes.json();
      const assignData = await assignRes.json();
      const timeData = await timeRes.json();
      const qData = await qRes.json();
      const typeData = await typeRes.json();

      setEmployees(empData);
      setProjects(projData);
      setAssignments(assignData);
      setLastUploadTime(timeData.last_upload_time);
      setQuestions(qData);
      setEvaluationTypes(typeData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // 검색 결과 변경 시 활성 인덱스 리셋
  useEffect(() => {
    setActiveEvaluateeIndex(0);
  }, [evaluateeSearchText]);

  useEffect(() => {
    setActiveEvaluatorIndex(0);
  }, [evaluatorSearchText]);

  // 피평가자 검색 필터링 (최대 10개 출력)
  const filteredEvaluatees = evaluateeSearchText.trim() === ''
    ? []
    : employees.filter(emp => {
        const query = evaluateeSearchText.toLowerCase();
        return (
          emp.name.toLowerCase().includes(query) ||
          (emp.team_name && emp.team_name.toLowerCase().includes(query)) ||
          emp.emp_id.toLowerCase().includes(query)
        );
      }).slice(0, 10);

  // 평가자 검색 필터링 (최대 10개 출력)
  const filteredEvaluators = evaluatorSearchText.trim() === ''
    ? []
    : employees.filter(emp => {
        const query = evaluatorSearchText.toLowerCase();
        return (
          emp.name.toLowerCase().includes(query) ||
          (emp.team_name && emp.team_name.toLowerCase().includes(query)) ||
          emp.emp_id.toLowerCase().includes(query)
        );
      }).slice(0, 10);

  // 엑셀 업로드 처리
  const handleExcelUpload = async (e) => {
    e.preventDefault();
    setUploadMsg('');
    setUploadError('');

    if (!file) {
      setUploadError('업로드할 엑셀 파일을 선택해 주세요.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/admin/upload-excel', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '엑셀 업로드에 실패했습니다.');
      }

      setUploadMsg(data.message);
      setFile(null);
      fetchData();
    } catch (err) {
      setUploadError(err.message);
    }
  };

  // 직접 사원 추가 처리
  const handleDirectCreateEmployee = async (e) => {
    e.preventDefault();
    setEmpCreateError('');
    setEmpCreateSuccess('');

    if (!newEmpId.trim() || !newEmpName.trim()) {
      setEmpCreateError('사번과 성명은 필수 입력 항목입니다.');
      return;
    }

    try {
      const response = await fetch('/api/admin/employees', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          emp_id: newEmpId.trim(),
          name: newEmpName.trim(),
          team_name: newEmpTeam.trim(),
          position: newEmpPosition.trim(),
          phone: newEmpPhone.trim(),
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '사원 추가에 실패했습니다.');
      }

      setEmpCreateSuccess(data.message || '사원이 성공적으로 등록되었습니다.');
      setNewEmpId('');
      setNewEmpName('');
      setNewEmpTeam('');
      setNewEmpPosition('');
      setNewEmpPhone('');
      fetchData();
    } catch (err) {
      setEmpCreateError(err.message);
    }
  };

  // 이미지 로드 대기 헬퍼
  const waitForImages = (element) => {
    const images = element.querySelectorAll('img');
    const promises = Array.from(images).map((img) => {
      if (img.complete) return Promise.resolve();
      return new Promise((resolve) => {
        img.onload = resolve;
        img.onerror = resolve;
      });
    });
    return Promise.all(promises);
  };

  // 개별 확인서 PDF 바이너리 생성 헬퍼 함수
  const generateSinglePDFBytes = async (assignmentId) => {
    const response = await fetch(`/api/admin/evaluations/${assignmentId}`);
    if (!response.ok) {
      throw new Error('평가 상세 정보를 가져오는데 실패했습니다.');
    }
    const data = await response.json();
    
    // 제출 일시 포맷팅
    const formatDateStr = (dateStr) => {
      if (!dateStr) return '';
      try {
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}년 ${month}월 ${day}일`;
      } catch (e) {
        return dateStr;
      }
    };

    const formattedDate = formatDateStr(data.submitted_at);
    const objectiveQuestions = data.questions.filter(q => q.is_essay === 0);
    const essayQuestions = data.questions.filter(q => q.is_essay === 1);

    // 객관식 점수 합계 계산
    let totalScore = 0;
    let maxScore = objectiveQuestions.length * 10;
    objectiveQuestions.forEach(q => {
      const ans = data.answers.find(a => a.question_id === q.question_id);
      if (ans && ans.score !== null) {
        totalScore += ans.score;
      }
    });

    const objectiveHtml = objectiveQuestions.map((q, idx) => {
      const ans = data.answers.find(a => a.question_id === q.question_id);
      const scoreText = ans && ans.score !== null ? `${ans.score}점 / 10점` : '-';
      
      return `
        <tr class="item-row">
          <td class="center-text">${idx + 1}</td>
          <td>
            <div class="q-main">${q.category}</div>
          </td>
          <td class="center-text font-bold">${scoreText}</td>
        </tr>
      `;
    }).join('');

    const totalRowHtml = `
      <tr class="item-row" style="background-color: #f8fafc; font-weight: bold;">
        <td class="center-text">${objectiveQuestions.length + 1}</td>
        <td>
          <div class="q-main" style="color: #1e293b;">객관식 점수 합계</div>
        </td>
        <td class="center-text" style="color: #1d4ed8; font-weight: 800;">${totalScore}점 / ${maxScore}점</td>
      </tr>
    `;

    const essayHtml = essayQuestions.map(q => {
      const ans = data.answers.find(a => a.question_id === q.question_id);
      const essayText = ans && ans.answer_text ? ans.answer_text.replace(/\n/g, '<br/>') : '';
      
      return `
        <tr class="essay-row">
          <td colspan="3" style="padding-top: 8px;">
            <div class="essay-box">
              <strong>[평가자 의견]</strong><br/>
              <div style="margin-top: 4px; line-height: 1.4; color: #1e293b;">
                ${essayText || '<span style="color: #94a3b8; font-style: italic;">작성된 평가자 의견이 없습니다.</span>'}
              </div>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    const questionsHtml = objectiveHtml + totalRowHtml + essayHtml;

    // 임시 컨테이너 생성 및 스타일 주입
    const container = document.createElement('div');
    container.style.position = 'absolute';
    container.style.left = '-9999px';
    container.style.top = '-9999px';
    container.style.width = '794px';
    container.style.boxSizing = 'border-box';
    container.style.backgroundColor = '#ffffff';

    container.innerHTML = `
      <style>
        .contract-container-pdf {
          width: 794px;
          box-sizing: border-box;
          padding: 40px 50px;
          background-color: #ffffff;
          position: relative;
          font-family: 'Malgun Gothic', '맑은 고딕', AppleSDGothicNeo, sans-serif;
          color: #0f172a;
        }
        .main-title {
          text-align: center;
          font-size: 24px;
          font-weight: 800;
          letter-spacing: 5px;
          margin-top: 10px;
          margin-bottom: 20px;
          color: #1e293b;
          border-bottom: 2px double #475569;
          padding-bottom: 10px;
        }
        .prologue {
          font-size: 13px;
          line-height: 1.6;
          text-align: justify;
          margin-bottom: 20px;
          color: #334155;
          text-indent: 10px;
        }
        .section-title {
          font-size: 14.5px;
          font-weight: 700;
          margin-top: 20px;
          margin-bottom: 8px;
          color: #0f172a;
          border-left: 4px solid #3b82f6;
          padding-left: 8px;
        }
        .info-table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 15px;
          font-size: 13px;
        }
        .info-table th, .info-table td {
          border: 1px solid #cbd5e1;
          padding: 8px 10px;
        }
        .info-table .label {
          background-color: #f8fafc;
          font-weight: 700;
          width: 120px;
          text-align: center;
          color: #475569;
        }
        .info-table .value {
          background-color: #ffffff;
        }
        .results-table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 20px;
          font-size: 13px;
        }
        .results-table th, .results-table td {
          border: 1px solid #cbd5e1;
          padding: 8px 10px;
        }
        .results-table th {
          background-color: #f8fafc;
          font-weight: 700;
          color: #475569;
        }
        .center-text {
          text-align: center;
        }
        .font-bold {
          font-weight: 700;
        }
        .q-main {
          font-weight: 700;
          color: #1e293b;
        }
        .essay-box {
          background-color: #f8fafc;
          border: 1px dashed #cbd5e1;
          border-radius: 4px;
          padding: 10px;
          font-size: 12.5px;
        }
        .sign-block {
          margin-top: 25px;
          text-align: center;
          border-top: 1px solid #e2e8f0;
          padding-top: 20px;
        }
        .date-str {
          font-size: 14px;
          font-weight: 700;
          letter-spacing: 2px;
          color: #475569;
          margin-bottom: 15px;
        }
        .signature-line {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 40px;
          font-size: 15px;
          position: relative;
          height: 40px;
        }
        .sig-wrapper {
          position: relative;
          width: 100px;
          height: 35px;
          display: flex;
          align-items: center;
        }
        .sig-img {
          max-width: 80px;
          max-height: 35px;
          position: absolute;
          left: 0;
          top: 50%;
          transform: translateY(-50%);
          mix-blend-mode: multiply;
        }
        .no-sig {
          color: #94a3b8;
          font-style: italic;
          font-size: 12px;
        }
      </style>
      <div class="contract-container-pdf">
        <h1 class="main-title">동 료 평 가 완 료 확 인 서</h1>
        
        <div class="prologue">
          위 평가자는 신의성실의 원칙에 입각하여 동료평가를 공정하고 객관적으로 완수하였으며,
          평가 대상자에 대한 다각적인 역량 평가와 서술식 피드백을 기록하여 제출하였음을 확인합니다.
        </div>

        <div class="section-title">1. 평가 개요</div>
        <table class="info-table">
          <tr>
            <td class="label">평가 프로젝트</td>
            <td class="value" colspan="3">${data.assignment.project_title}</td>
          </tr>
          <tr>
            <td class="label">피평가자(대상자)</td>
            <td class="value">${data.assignment.evaluatee_name} ${data.assignment.evaluatee_position || '사원'}</td>
            <td class="label">소속 부서</td>
            <td class="value">${data.assignment.evaluatee_team || '부서없음'}</td>
          </tr>
          <tr>
            <td class="label">평가자</td>
            <td class="value">${data.assignment.evaluator_name} ${data.assignment.evaluator_position || '사원'}</td>
            <td class="label">소속 부서</td>
            <td class="value">${data.assignment.evaluator_team || '부서없음'}</td>
          </tr>
        </table>

        <div class="section-title">2. 평가 상세 내역</div>
        <table class="results-table">
          <thead>
            <tr>
              <th style="width: 50px;">순번</th>
              <th>평가항목</th>
              <th style="width: 140px;">평가 결과</th>
            </tr>
          </thead>
          <tbody>
            ${questionsHtml}
          </tbody>
        </table>

        <div class="sign-block">
          <div class="date-str">${formattedDate}</div>
          <div class="signature-line">
            <span>평가자: <strong>${data.assignment.evaluator_name}</strong></span>
            <div class="sig-wrapper">
              ${data.signature_data ? `<img src="${data.signature_data}" alt="서명" class="sig-img" />` : '<span class="no-sig">(서명 생략)</span>'}
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(container);

    try {
      await waitForImages(container);
      
      const canvas = await html2canvas(container, {
        scale: 2,
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#ffffff'
      });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      pdf.addImage(imgData, 'PNG', 0, 0, 210, 297);
      
      const arrayBuffer = pdf.output('arraybuffer');
      
      return {
        arrayBuffer,
        pdfInstance: pdf,
        assignmentInfo: data.assignment
      };
    } finally {
      document.body.removeChild(container);
    }
  };

  // 개별 평가지 PDF 직접 다운로드 처리
  const handlePrintEvaluation = async (assignmentId) => {
    setPdfLoading(true);
    setPdfLoadingMsg('PDF 문서 생성 중...');
    try {
      const { pdfInstance, assignmentInfo } = await generateSinglePDFBytes(assignmentId);
      const filename = `${assignmentInfo.evaluatee_name}_${assignmentInfo.evaluator_name}_동료평가완료확인서.pdf`;
      pdfInstance.save(filename);
    } catch (err) {
      alert('PDF 생성에 실패했습니다: ' + err.message);
    } finally {
      setPdfLoading(false);
      setPdfLoadingMsg('');
    }
  };

  // 일괄 완료확인서 병합 PDF 생성 및 다운로드 처리
  const handleBulkPDFDownload = async (projectId, projectTitle) => {
    const completedAssigns = assignments.filter(
      (a) => a.project_id === projectId && a.status === 'completed'
    );

    if (completedAssigns.length === 0) {
      alert('완료된 평가 완료확인서가 없습니다.');
      return;
    }

    setPdfLoading(true);
    setPdfLoadingMsg('PDF 병합 준비 중...');

    try {
      const mergedPdf = await PDFDocument.create();
      
      for (let i = 0; i < completedAssigns.length; i++) {
        const item = completedAssigns[i];
        setPdfLoadingMsg(`PDF 생성 중... (${i + 1}/${completedAssigns.length}명 완료)`);
        
        const { arrayBuffer } = await generateSinglePDFBytes(item.assignment_id);
        const subPdf = await PDFDocument.load(arrayBuffer);
        const copiedPages = await mergedPdf.copyPages(subPdf, subPdf.getPageIndices());
        copiedPages.forEach((page) => {
          mergedPdf.addPage(page);
        });
      }

      setPdfLoadingMsg('PDF 병합 완료 및 다운로드 준비 중...');
      const mergedPdfBytes = await mergedPdf.save();
      const blob = new Blob([mergedPdfBytes], { type: 'application/pdf' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `${projectTitle}_동료평가완료확인서_일괄.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      alert('일괄 PDF 병합에 실패했습니다: ' + err.message);
    } finally {
      setPdfLoading(false);
      setPdfLoadingMsg('');
    }
  };


  // 평가 프로젝트 생성
  const handleCreateProject = async (e) => {
    e.preventDefault();
    setProjCreateError('');
    setProjCreateSuccess('');

    if (!projectEvaluateeId) {
      setProjCreateError('피평가자를 선택해 주세요.');
      return;
    }

    try {
      const response = await fetch('/api/admin/projects', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          evaluatee_id: parseInt(projectEvaluateeId, 10),
          evaluation_type: evaluationType,
          start_date: startDate,
          end_date: endDate
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '프로젝트 생성에 실패했습니다.');
      }

      setProjCreateSuccess(data.message);
      setProjectEvaluateeId('');
      setEvaluateeSearchText('');
      setEvaluationType(evaluationTypes[0] || '동료사원 평가');
      fetchData();
    } catch (err) {
      setProjCreateError(err.message);
    }
  };

  // 평가 종류 추가 핸들러
  const handleAddEvalType = async (e) => {
    e.preventDefault();
    setEvalTypeError('');
    setEvalTypeSuccess('');

    if (!newEvalTypeName || !newEvalTypeName.trim()) {
      setEvalTypeError('평가 종류 이름을 입력해 주세요.');
      return;
    }

    try {
      const response = await fetch('/api/admin/evaluation-types', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newEvalTypeName.trim()
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '평가 종류 추가에 실패했습니다.');
      }

      setEvalTypeSuccess(data.message || '평가 종류가 추가되었습니다.');
      setNewEvalTypeName('');
      fetchData();
    } catch (err) {
      setEvalTypeError(err.message);
    }
  };

  // 평가 종류 삭제 핸들러
  const handleDeleteEvalType = async (name) => {
    if (!window.confirm(`'${name}' 평가 종류를 정말 삭제하시겠습니까?\n주의: 기존에 이 종류로 생성된 프로젝트나 문항이 있으면 삭제할 수 없습니다.`)) {
      return;
    }
    setEvalTypeError('');
    setEvalTypeSuccess('');

    try {
      const response = await fetch('/api/admin/evaluation-types', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: name
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '평가 종류 삭제에 실패했습니다.');
      }

      setEvalTypeSuccess(data.message || '평가 종류가 삭제되었습니다.');
      fetchData();
    } catch (err) {
      setEvalTypeError(err.message);
    }
  };

  // 직접 검색 트랙: 배정 대기 목록에 평가자 추가
  const handleAddEvaluatorTag = (emp) => {
    if (!selectedProjectId) {
      alert('평가 프로젝트를 먼저 선택해 주세요.');
      return;
    }

    if (selectedEvaluators.some((item) => item.id === emp.id)) {
      alert('이미 대기 목록에 추가된 사원입니다.');
      return;
    }

    const proj = projects.find((p) => p.project_id === parseInt(selectedProjectId, 10));
    if (proj && proj.evaluatee_id === emp.id) {
      alert('자기 자신을 평가 대상자로 지정할 수 없습니다.');
      return;
    }

    const alreadyAssigned = assignments.some(
      (a) => a.project_id === parseInt(selectedProjectId, 10) && a.evaluator_id === emp.id
    );
    if (alreadyAssigned) {
      alert('이미 이 프로젝트에 배정되어 있는 평가자입니다.');
      return;
    }

    setSelectedEvaluators((prev) => [...prev, emp]);
  };

  // 직접 검색 트랙: 대기 목록 태그 제거
  const handleRemoveEvaluatorTag = (empId) => {
    setSelectedEvaluators((prev) => prev.filter((item) => item.id !== empId));
  };

  // 직접 검색 트랙: 배정 제출
  const handleCreateAssignment = async (e) => {
    e.preventDefault();
    setAssignmentError('');
    setAssignmentSuccess('');

    if (!selectedProjectId) {
      setAssignmentError('평가 프로젝트를 선택해 주세요.');
      return;
    }

    if (selectedEvaluators.length === 0) {
      setAssignmentError('배정할 평가자를 한 명 이상 추가해 주세요.');
      return;
    }

    const evaluatorIds = selectedEvaluators.map((emp) => emp.id);

    try {
      const response = await fetch('/api/admin/assignments/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: parseInt(selectedProjectId, 10),
          evaluator_ids: evaluatorIds
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '배정 추가에 실패했습니다.');
      }

      setAssignmentSuccess(data.message);
      setSelectedEvaluators([]); // 대기 목록 초기화
      fetchData();
    } catch (err) {
      setAssignmentError(err.message);
    }
  };

  // 엑셀 붙여넣기 트랙: 텍스트 파싱 및 동명이인 부서 기반 자동 매핑
  const handleParseExcelList = () => {
    if (!selectedProjectId) {
      alert('평가 프로젝트를 먼저 선택해 주세요.');
      return;
    }

    if (!excelPasteText.trim()) {
      alert('붙여넣을 텍스트를 입력해 주세요.');
      return;
    }

    const currentProj = projects.find(p => p.project_id === parseInt(selectedProjectId, 10));
    const evaluateeId = currentProj ? currentProj.evaluatee_id : null;
    const evaluateeTeam = currentProj ? currentProj.evaluatee_team : '';

    // 줄바꿈, 쉼표, 세미콜론, 탭 등으로 문자열 분할 후 공백 제거
    const names = excelPasteText
      .split(/[\n,;\t]/)
      .map(n => n.replace(/\r/g, '').trim())
      .filter(n => n.length > 0);

    const previews = names.map(inputName => {
      // 1. 이름으로 사원 검색
      const matched = employees.filter(emp => emp.name === inputName);

      if (matched.length === 0) {
        return {
          inputName,
          matchedEmp: null,
          status: 'not_found',
          candidates: []
        };
      }

      // 2. 피평가자 본인은 평가자 후보에서 제외
      const candidates = matched.filter(emp => emp.id !== evaluateeId);
      if (candidates.length === 0) {
        return {
          inputName,
          matchedEmp: null,
          status: 'self',
          candidates: []
        };
      }

      // 3. 단일 검색 매칭 성공
      if (candidates.length === 1) {
        const emp = candidates[0];
        const alreadyAssigned = assignments.some(
          (a) => a.project_id === parseInt(selectedProjectId, 10) && a.evaluator_id === emp.id
        );
        return {
          inputName,
          matchedEmp: emp,
          status: alreadyAssigned ? 'already_assigned' : 'success',
          candidates: [emp]
        };
      }

      // 4. 다중 매칭 (동명이인 발생) -> 피평가자 부서(team_name) 기반 매핑
      // 피평가자 부서와 정확히 일치하거나 서로를 포함하는 경우
      const exactTeamMatched = candidates.filter(
        emp => emp.team_name && evaluateeTeam && emp.team_name === evaluateeTeam
      );
      
      const partialTeamMatched = candidates.filter(
        emp => emp.team_name && evaluateeTeam && 
               (emp.team_name.includes(evaluateeTeam) || evaluateeTeam.includes(emp.team_name))
      );

      let selectedCandidate = candidates[0];
      let status = 'duplicate';

      if (exactTeamMatched.length === 1) {
        selectedCandidate = exactTeamMatched[0];
        status = 'success'; // 부서 정확 일치 시 자동 매핑 성공 처리
      } else if (partialTeamMatched.length === 1) {
        selectedCandidate = partialTeamMatched[0];
        status = 'success'; // 부서 부분 일치 시 자동 매핑 성공 처리
      }

      const alreadyAssigned = assignments.some(
        (a) => a.project_id === parseInt(selectedProjectId, 10) && a.evaluator_id === selectedCandidate.id
      );

      return {
        inputName,
        matchedEmp: selectedCandidate,
        status: alreadyAssigned ? 'already_assigned' : status,
        candidates: candidates
      };
    });

    setMappingPreview(previews);
  };

  // 엑셀 붙여넣기 트랙: 동명이인 수동 선택 변경 처리
  const handleResolveDuplicate = (inputName, targetId) => {
    setMappingPreview((prev) => 
      prev.map((p) => {
        if (p.inputName === inputName) {
          const newMatched = p.candidates.find((c) => c.id === targetId);
          const alreadyAssigned = assignments.some(
            (a) => a.project_id === parseInt(selectedProjectId, 10) && a.evaluator_id === targetId
          );
          return {
            ...p,
            matchedEmp: newMatched,
            status: alreadyAssigned ? 'already_assigned' : 'success'
          };
        }
        return p;
      })
    );
  };

  // 엑셀 붙여넣기 트랙: 일괄 배정 제출
  const handleCreateAssignmentBulk = async (e) => {
    e.preventDefault();
    setAssignmentError('');
    setAssignmentSuccess('');

    // 유효하게 매핑이 성공했거나 동명이인 상태의 사원 ID 추출
    const validPreviews = mappingPreview.filter(p => p.status === 'success' || p.status === 'duplicate');
    if (validPreviews.length === 0) {
      setAssignmentError('배정할 수 있는 유효한 사원이 없습니다.');
      return;
    }

    const evaluatorIds = validPreviews.map(p => p.matchedEmp.id);

    try {
      const response = await fetch('/api/admin/assignments/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: parseInt(selectedProjectId, 10),
          evaluator_ids: evaluatorIds
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '배정 추가에 실패했습니다.');
      }

      setAssignmentSuccess(data.message);
      setExcelPasteText('');
      setMappingPreview([]);
      fetchData();
    } catch (err) {
      setAssignmentError(err.message);
    }
  };

  // 프로젝트 삭제
  const handleDeleteProject = async (projId) => {
    if (!confirm('해당 평가 프로젝트를 삭제하시겠습니까? 삭제 시 하위 배정 및 제출된 평가가 모두 영구 삭제됩니다.')) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/projects/${projId}`, {
        method: 'DELETE',
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '프로젝트 삭제에 실패했습니다.');
      }

      if (parseInt(selectedProjectId, 10) === projId) {
        setSelectedProjectId('');
        setSelectedEvaluators([]);
        setMappingPreview([]);
      }
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 배정 취소(삭제)
  const handleDeleteAssignment = async (assignId) => {
    if (!confirm('정말 해당 평가 배정을 삭제하시겠습니까?')) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/assignments/${assignId}`, {
        method: 'DELETE',
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '배정 삭제에 실패했습니다.');
      }

      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 배정 진행 상태 강제 변경 (관리자 기능)
  const handleStatusChange = async (assignId, newStatus) => {
    try {
      const response = await fetch(`/api/admin/assignments/${assignId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          status: newStatus
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '상태 변경에 실패했습니다.');
      }

      alert(data.message);
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 특정 프로젝트의 배정된 평가자들의 전화번호 일괄 복사
  const handleCopyEvaluatorPhones = (projId) => {
    const projAssignments = assignments.filter((a) => a.project_id === projId);
    
    // 전화번호가 있고 유효한 값인 경우만 추출
    const phoneNumbers = projAssignments
      .map((a) => a.evaluator_phone)
      .filter((phone) => phone && phone.trim() !== '')
      .map((phone) => phone.trim());

    if (phoneNumbers.length === 0) {
      alert('배정된 평가자들 중 등록된 전화번호가 없습니다. 사원명부 엑셀 재업로드를 통해 사원별 전화번호가 정상 연동되었는지 확인해 주세요.');
      return;
    }

    // 엑셀에서 세로 열로 복사한 것처럼 줄바꿈(\n) 구분자로 클립보드 복사
    const joinedPhones = phoneNumbers.join('\n');
    
    navigator.clipboard.writeText(joinedPhones)
      .then(() => {
        alert(`배정된 평가자 ${phoneNumbers.length}명의 전화번호가 클립보드에 복사되었습니다.\n\n[복사된 번호 목록]\n${joinedPhones}\n\n엑셀 열에 세로로 붙여넣거나 단체 문자 입력창에 붙여넣기(Ctrl+V) 하세요.`);
      })
      .catch((err) => {
        console.error('클립보드 복사 실패:', err);
        alert('전화번호 복사에 실패했습니다.');
      });
  };

  // 평가 문항 등록
  const handleCreateQuestion = async (e) => {
    e.preventDefault();
    if (!questionText.trim() || !questionCategory.trim()) {
      alert('문항 제목과 설명을 입력해 주세요.');
      return;
    }

    try {
      const response = await fetch('/api/admin/questions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question_text: questionText,
          question_sub_text: questionSubText,
          category: questionCategory,
          is_essay: parseInt(questionIsEssay, 10),
          evaluation_type: questionEvaluationType
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '문항 추가에 실패했습니다.');
      }

      alert(data.message);
      setQuestionText('');
      setQuestionSubText('');
      setQuestionCategory('');
      setQuestionIsEssay(0);
      setQuestionEvaluationType(evaluationTypes[0] || '동료사원 평가');
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 평가 문항 수정 모드 진입
  const handleStartEditQuestion = (q) => {
    setEditingQuestionId(q.id);
    setEditQuestionText(q.question_text);
    setEditQuestionSubText(q.question_sub_text || '');
    setEditQuestionCategory(q.category);
    setEditQuestionIsEssay(q.is_essay);
    setEditQuestionEvaluationType(q.evaluation_type || (evaluationTypes[0] || '동료사원 평가'));
  };

  // 평가 문항 수정 저장
  const handleSaveQuestion = async (qId) => {
    if (!editQuestionText.trim() || !editQuestionCategory.trim()) {
      alert('문항 제목과 설명을 입력해 주세요.');
      return;
    }

    try {
      const response = await fetch(`/api/admin/questions/${qId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question_text: editQuestionText,
          question_sub_text: editQuestionSubText,
          category: editQuestionCategory,
          is_essay: parseInt(editQuestionIsEssay, 10),
          evaluation_type: editQuestionEvaluationType
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '문항 수정에 실패했습니다.');
      }

      alert(data.message);
      setEditingQuestionId(null);
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 평가 문항 삭제
  const handleDeleteQuestion = async (qId) => {
    if (!confirm('해당 평가 문항을 삭제하시겠습니까? 기 제출된 답변이 있는 문항은 비활성화 처리됩니다.')) {
      return;
    }

    try {
      const response = await fetch(`/api/admin/questions/${qId}`, {
        method: 'DELETE'
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '문항 삭제에 실패했습니다.');
      }

      alert(data.message);
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 비활성화 문항 활성화
  const handleActivateQuestion = async (qId) => {
    try {
      const response = await fetch(`/api/admin/questions/${qId}/activate`, {
        method: 'PATCH'
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '문항 활성화에 실패했습니다.');
      }

      alert(data.message);
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  // 평가 문항 순서 변경 (위/아래 이동)
  const handleMoveQuestion = async (index, direction) => {
    const newQuestions = [...questions];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;

    if (targetIndex < 0 || targetIndex >= newQuestions.length) {
      return;
    }

    const temp = newQuestions[index];
    newQuestions[index] = newQuestions[targetIndex];
    newQuestions[targetIndex] = temp;

    setQuestions(newQuestions);

    const questionIds = newQuestions.map(q => q.id);
    try {
      const response = await fetch('/api/admin/questions/reorder', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question_ids: questionIds
        })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || '순서 조정에 실패했습니다.');
      }
      fetchData();
    } catch (err) {
      alert(err.message);
      fetchData();
    }
  };

  return (
    <>
      <div className="header-bar" style={{ borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0' }}>
        <span className="header-title" style={{ color: 'var(--danger)', fontWeight: '800' }}>Smart Evaluator 관리자 대시보드</span>
        <button className="header-btn" onClick={onLogout} style={{ border: '1px solid var(--border-color)', padding: '6px 12px' }}>로그아웃</button>
      </div>

      <div style={{
        display: 'flex',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid var(--border-color)',
        padding: '0 24px'
      }}>
        <div
          onClick={() => {
            setActiveTab('employees');
            setEmployeeSearchText('');
          }}
          style={{
            padding: '14px 20px',
            fontSize: '14px',
            fontWeight: '700',
            cursor: 'pointer',
            color: activeTab === 'employees' ? 'var(--primary-color)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'employees' ? '3px solid var(--primary-color)' : '3px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          사원명부 관리
        </div>
        <div
          onClick={() => {
            setActiveTab('projects');
            setProjectSearchText('');
            setProjectStatusFilter('all');
            setProjectSearchTextForAssignment('');
            setSelectedProjectId('');
            setSelectedEvaluators([]);
            setMappingPreview([]);
          }}
          style={{
            padding: '14px 20px',
            fontSize: '14px',
            fontWeight: '700',
            cursor: 'pointer',
            color: activeTab === 'projects' ? 'var(--primary-color)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'projects' ? '3px solid var(--primary-color)' : '3px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          평가 프로젝트 관리
        </div>
        <div
          onClick={() => setActiveTab('questions')}
          style={{
            padding: '14px 20px',
            fontSize: '14px',
            fontWeight: '700',
            cursor: 'pointer',
            color: activeTab === 'questions' ? 'var(--primary-color)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'questions' ? '3px solid var(--primary-color)' : '3px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          평가 문항 설정
        </div>
      </div>


      <div className="page-content" style={{ padding: '24px', backgroundColor: 'var(--background-color)', flex: 1, overflowY: 'auto' }}>
        
        {/* === 사원명부 관리 탭 === */}
        {activeTab === 'employees' && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(400px, 460px) 1fr',
            gap: '24px',
            alignItems: 'start'
          }}>
            {/* 좌측 영역: 사원명부 업로드 및 직접 추가 */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* 1. 사원명부 엑셀 업로드 */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', borderLeft: '4px solid var(--secondary-color)', paddingLeft: '8px' }}>
                  사원명부 엑셀 업로드
                </h3>

                {/* 실시간 업로드 현황 모니터링 배너 */}
                <div style={{
                  backgroundColor: 'var(--primary-light)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '12px 16px',
                  marginBottom: '16px',
                  fontSize: '13px',
                  color: 'var(--text-secondary)',
                  lineHeight: '1.6'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>등록된 총 사원 수:</span>
                    <strong style={{ color: 'var(--primary-color)', fontSize: '14px' }}>{employees.length}명</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px' }}>
                    <span>최근 엑셀 업로드 일시:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>{lastUploadTime}</strong>
                  </div>
                </div>
                
                {uploadMsg && (
                  <div className="alert alert-success" style={{ marginBottom: '12px' }}>
                    <span>{uploadMsg}</span>
                  </div>
                )}
                {uploadError && (
                  <div className="alert alert-error" style={{ marginBottom: '12px' }}>
                    <span>{uploadError}</span>
                  </div>
                )}

                <form onSubmit={handleExcelUpload} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div className="input-group">
                    <input
                      type="file"
                      accept=".xls,.xlsx"
                      className="input-field"
                      style={{ padding: '8px 12px', fontSize: '13px' }}
                      onChange={(e) => setFile(e.target.files[0])}
                    />
                  </div>
                  <button className="btn btn-secondary" type="submit" style={{ padding: '10px', fontSize: '14px' }}>
                    엑셀 업로드 반영
                  </button>
                </form>
              </div>

              {/* 2. 직접 사원 추가 */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', borderLeft: '4px solid var(--primary-color)', paddingLeft: '8px' }}>
                  직접 사원 추가
                </h3>

                {empCreateSuccess && (
                  <div className="alert alert-success" style={{ marginBottom: '12px' }}>
                    <span>{empCreateSuccess}</span>
                  </div>
                )}
                {empCreateError && (
                  <div className="alert alert-error" style={{ marginBottom: '12px' }}>
                    <span>{empCreateError}</span>
                  </div>
                )}

                <form onSubmit={handleDirectCreateEmployee} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div className="input-group">
                    <label className="input-label" style={{ fontSize: '12px' }}>사번 (필수)</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="예: 20260101"
                      value={newEmpId}
                      onChange={(e) => setNewEmpId(e.target.value)}
                      style={{ padding: '8px 12px', fontSize: '13px' }}
                      required
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label" style={{ fontSize: '12px' }}>성명 (필수)</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="예: 홍길동"
                      value={newEmpName}
                      onChange={(e) => setNewEmpName(e.target.value)}
                      style={{ padding: '8px 12px', fontSize: '13px' }}
                      required
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label" style={{ fontSize: '12px' }}>부서 (선택)</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="예: 인사팀"
                      value={newEmpTeam}
                      onChange={(e) => setNewEmpTeam(e.target.value)}
                      style={{ padding: '8px 12px', fontSize: '13px' }}
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label" style={{ fontSize: '12px' }}>직급 (선택)</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="예: 대리"
                      value={newEmpPosition}
                      onChange={(e) => setNewEmpPosition(e.target.value)}
                      style={{ padding: '8px 12px', fontSize: '13px' }}
                    />
                  </div>
                  <div className="input-group">
                    <label className="input-label" style={{ fontSize: '12px' }}>연락처 (선택)</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="예: 010-1234-5678"
                      value={newEmpPhone}
                      onChange={(e) => setNewEmpPhone(e.target.value)}
                      style={{ padding: '8px 12px', fontSize: '13px' }}
                    />
                  </div>
                  <button className="btn btn-primary" type="submit" style={{ padding: '10px', fontSize: '14px', marginTop: '4px' }}>
                    사원 등록
                  </button>
                </form>
              </div>

            </div>

            {/* 우측 영역: 등록된 사원 명단 검색 테이블 */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', borderLeft: '4px solid var(--success)', paddingLeft: '8px' }}>
                등록된 사원 명단 ({employees.length}명)
              </h3>
              
              <div style={{ marginBottom: '16px' }}>
                <input
                  type="text"
                  className="input-field"
                  placeholder="성명, 부서, 직급, 사번으로 사원 검색..."
                  value={employeeSearchText}
                  onChange={(e) => setEmployeeSearchText(e.target.value)}
                  style={{ padding: '8px 12px', fontSize: '13px', width: '100%' }}
                />
              </div>

              <div style={{ overflowX: 'auto', maxHeight: '550px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border-color)', textAlign: 'left', backgroundColor: '#f8fafc' }}>
                      <th style={{ padding: '12px 10px', fontWeight: '600', color: 'var(--text-secondary)' }}>사번</th>
                      <th style={{ padding: '12px 10px', fontWeight: '600', color: 'var(--text-secondary)' }}>성명</th>
                      <th style={{ padding: '12px 10px', fontWeight: '600', color: 'var(--text-secondary)' }}>부서</th>
                      <th style={{ padding: '12px 10px', fontWeight: '600', color: 'var(--text-secondary)' }}>직급</th>
                      <th style={{ padding: '12px 10px', fontWeight: '600', color: 'var(--text-secondary)' }}>연락처</th>
                    </tr>
                  </thead>
                  <tbody>
                    {employees.filter(emp => {
                      const q = employeeSearchText.toLowerCase().trim();
                      if (!q) return true;
                      return (
                        emp.name.toLowerCase().includes(q) ||
                        emp.emp_id.toLowerCase().includes(q) ||
                        (emp.team_name && emp.team_name.toLowerCase().includes(q)) ||
                        (emp.position && emp.position.toLowerCase().includes(q))
                      );
                    }).length === 0 ? (
                      <tr>
                        <td colSpan="5" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                          일치하는 사원 정보가 존재하지 않습니다.
                        </td>
                      </tr>
                    ) : (
                      employees.filter(emp => {
                        const q = employeeSearchText.toLowerCase().trim();
                        if (!q) return true;
                        return (
                          emp.name.toLowerCase().includes(q) ||
                          emp.emp_id.toLowerCase().includes(q) ||
                          (emp.team_name && emp.team_name.toLowerCase().includes(q)) ||
                          (emp.position && emp.position.toLowerCase().includes(q))
                        );
                      }).map((emp) => (
                        <tr key={emp.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '10px', color: 'var(--text-secondary)', fontWeight: 'bold' }}>{emp.emp_id}</td>
                          <td style={{ padding: '10px', fontWeight: '600' }}>{emp.name}</td>
                          <td style={{ padding: '10px' }}>{emp.team_name || '-'}</td>
                          <td style={{ padding: '10px' }}>{emp.position || '-'}</td>
                          <td style={{ padding: '10px', color: 'var(--text-secondary)' }}>{emp.phone || '-'}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* === 평가 프로젝트 관리 탭 === */}
        {activeTab === 'projects' && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(400px, 460px) 1fr',
            gap: '24px',
            alignItems: 'start'
          }}>
            
            {/* 좌측 영역 (설정 및 배정 제어 영역) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* 1. 동료평가 프로젝트 생성 */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', borderLeft: '4px solid var(--primary-color)', paddingLeft: '8px' }}>
                  동료평가 프로젝트 생성
                </h3>

                {projCreateSuccess && (
                  <div className="alert alert-success" style={{ marginBottom: '12px' }}>
                    <span>{projCreateSuccess}</span>
                  </div>
                )}
                {projCreateError && (
                  <div className="alert alert-error" style={{ marginBottom: '12px' }}>
                    <span>{projCreateError}</span>
                  </div>
                )}

                <form onSubmit={handleCreateProject} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div className="input-group" style={{ position: 'relative' }}>
                    <label className="input-label" style={{ fontSize: '13px' }}>피평가자 검색 및 선택</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="성명, 부서 또는 사번으로 검색"
                      value={evaluateeSearchText}
                      onChange={(e) => {
                        setEvaluateeSearchText(e.target.value);
                        setShowEvaluateeDropdown(true);
                        setProjectEvaluateeId('');
                      }}
                      onFocus={() => setShowEvaluateeDropdown(true)}
                      onBlur={() => setTimeout(() => setShowEvaluateeDropdown(false), 200)}
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowDown') {
                          e.preventDefault();
                          setActiveEvaluateeIndex((prev) => 
                            prev < filteredEvaluatees.length - 1 ? prev + 1 : prev
                          );
                        } else if (e.key === 'ArrowUp') {
                          e.preventDefault();
                          setActiveEvaluateeIndex((prev) => 
                            prev > 0 ? prev - 1 : prev
                          );
                        } else if (e.key === 'Enter') {
                          e.preventDefault();
                          if (filteredEvaluatees.length > 0) {
                            const emp = filteredEvaluatees[activeEvaluateeIndex];
                            setProjectEvaluateeId(emp.id);
                            setEvaluateeSearchText(`[${emp.team_name || '부서없음'}] ${emp.name} ${emp.position || ''} (${emp.emp_id})`);
                            setShowEvaluateeDropdown(false);
                          }
                        } else if (e.key === 'Escape') {
                          setShowEvaluateeDropdown(false);
                        }
                      }}
                    />
                    {showEvaluateeDropdown && evaluateeSearchText.trim() !== '' && (
                      <div style={{
                        position: 'absolute',
                        top: '100%',
                        left: 0,
                        right: 0,
                        backgroundColor: '#ffffff',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-sm)',
                        maxHeight: '220px',
                        overflowY: 'auto',
                        zIndex: 100,
                        boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                      }}>
                        {filteredEvaluatees.length === 0 ? (
                          <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center' }}>
                            검색 결과가 없습니다.
                          </div>
                        ) : (
                          filteredEvaluatees.map((emp, index) => {
                            const isHighlighted = index === activeEvaluateeIndex;
                            return (
                              <div
                                key={emp.id}
                                onMouseDown={() => {
                                  setProjectEvaluateeId(emp.id);
                                  setEvaluateeSearchText(`[${emp.team_name || '부서없음'}] ${emp.name} ${emp.position || ''} (${emp.emp_id})`);
                                  setShowEvaluateeDropdown(false);
                                }}
                                style={{
                                  padding: '10px 12px',
                                  cursor: 'pointer',
                                  borderBottom: '1px solid #f1f5f9',
                                  fontSize: '13px',
                                  textAlign: 'left',
                                  backgroundColor: isHighlighted ? '#eff6ff' : 'transparent',
                                  color: isHighlighted ? 'var(--primary-color)' : 'var(--text-primary)'
                                }}
                                onMouseEnter={() => setActiveEvaluateeIndex(index)}
                              >
                                <strong>{emp.name}</strong> {emp.position} <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>({emp.team_name} | {emp.emp_id})</span>
                                {isHighlighted && <span style={{ float: 'right', fontSize: '10px', color: 'var(--primary-color)', fontWeight: 'bold' }}>Enter로 선택</span>}
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>

                  <div className="input-group">
                    <label className="input-label" style={{ fontSize: '13px' }}>평가 종류 선택</label>
                    <select
                      className="input-field"
                      value={evaluationType}
                      onChange={(e) => setEvaluationType(e.target.value)}
                      style={{ backgroundColor: 'var(--surface-color)', padding: '10px' }}
                    >
                      {evaluationTypes.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  </div>

                  <div style={{ display: 'flex', gap: '12px' }}>
                    <div className="input-group" style={{ flex: 1 }}>
                      <label className="input-label" style={{ fontSize: '12px' }}>평가 시작일</label>
                      <input
                        type="date"
                        className="input-field"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                        style={{ padding: '8px 10px', fontSize: '13px' }}
                        required
                      />
                    </div>
                    <div className="input-group" style={{ flex: 1 }}>
                      <label className="input-label" style={{ fontSize: '12px' }}>평가 종료일</label>
                      <input
                        type="date"
                        className="input-field"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        style={{ padding: '8px 10px', fontSize: '13px' }}
                        required
                      />
                    </div>
                  </div>

                  <button className="btn btn-primary" type="submit" style={{ padding: '10px', fontSize: '14px' }}>
                    평가 프로젝트 생성
                  </button>
                </form>
              </div>

              {/* 1-2. 평가 종류 관리 */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', borderLeft: '4px solid var(--primary-color)', paddingLeft: '8px' }}>
                  평가 종류 관리
                </h3>

                {evalTypeSuccess && (
                  <div className="alert alert-success" style={{ marginBottom: '12px' }}>
                    <span>{evalTypeSuccess}</span>
                  </div>
                )}
                {evalTypeError && (
                  <div className="alert alert-error" style={{ marginBottom: '12px' }}>
                    <span>{evalTypeError}</span>
                  </div>
                )}

                <form onSubmit={handleAddEvalType} style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="새 평가 종류 이름"
                    value={newEvalTypeName}
                    onChange={(e) => setNewEvalTypeName(e.target.value)}
                    style={{ flex: 1, padding: '8px 10px', fontSize: '13px' }}
                    required
                  />
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ padding: '8px 16px', fontSize: '13px', whiteSpace: 'nowrap' }}
                  >
                    추가
                  </button>
                </form>

                <div style={{
                  maxHeight: '150px',
                  overflowY: 'auto',
                  border: '1px solid var(--border-color)',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: '#f8fafc'
                }}>
                  {evaluationTypes.map((t) => (
                    <div
                      key={t}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '8px 12px',
                        borderBottom: '1px solid #e2e8f0',
                        fontSize: '13px'
                      }}
                    >
                      <span style={{ fontWeight: '500', color: 'var(--text-primary)' }}>{t}</span>
                      <button
                        type="button"
                        onClick={() => handleDeleteEvalType(t)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#ef4444',
                          cursor: 'pointer',
                          fontSize: '12px',
                          fontWeight: '600',
                          padding: '2px 4px'
                        }}
                      >
                        삭제
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* 2. 평가 관계 배정 (투 트랙 운영) */}
              <div className="card" style={{ padding: '20px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '14px', borderLeft: '4px solid var(--warning)', paddingLeft: '8px' }}>
                  평가 프로젝트에 평가자 배정
                </h3>

                {assignmentSuccess && (
                  <div className="alert alert-success" style={{ marginBottom: '12px' }}>
                    <span>{assignmentSuccess}</span>
                  </div>
                )}
                {assignmentError && (
                  <div className="alert alert-error" style={{ marginBottom: '12px' }}>
                    <span>{assignmentError}</span>
                  </div>
                )}

                {/* 투 트랙 전환 탭 */}
                <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: '16px' }}>
                  <div
                    onClick={() => { setActiveTrack('search'); setAssignmentError(''); setAssignmentSuccess(''); }}
                    style={{
                      flex: 1,
                      textAlign: 'center',
                      padding: '8px',
                      fontSize: '13px',
                      fontWeight: '600',
                      cursor: 'pointer',
                      color: activeTrack === 'search' ? 'var(--primary-color)' : 'var(--text-secondary)',
                      borderBottom: activeTrack === 'search' ? '2px solid var(--primary-color)' : '2px solid transparent'
                    }}
                  >
                    직접 검색 추가
                  </div>
                  <div
                    onClick={() => { setActiveTrack('excel'); setAssignmentError(''); setAssignmentSuccess(''); }}
                    style={{
                      flex: 1,
                      textAlign: 'center',
                      padding: '8px',
                      fontSize: '13px',
                      fontWeight: '600',
                      cursor: 'pointer',
                      color: activeTrack === 'excel' ? 'var(--primary-color)' : 'var(--text-secondary)',
                      borderBottom: activeTrack === 'excel' ? '2px solid var(--primary-color)' : '2px solid transparent'
                    }}
                  >
                    엑셀 복사/일괄 추가
                  </div>
                </div>

                {/* 공통: 평가 프로젝트 선택 (검색 자동완성 UI) */}
                <div className="input-group" style={{ marginBottom: '14px', position: 'relative' }}>
                  <label className="input-label" style={{ fontSize: '13px' }}>평가 대상 프로젝트 검색 및 선택</label>
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="피평가자명, 부서, 프로젝트명으로 검색"
                      value={projectSearchTextForAssignment}
                      onChange={(e) => {
                        setProjectSearchTextForAssignment(e.target.value);
                        setShowProjectDropdownForAssignment(true);
                        setSelectedProjectId('');
                        setSelectedEvaluators([]);
                        setExcelPasteText('');
                        setMappingPreview([]);
                      }}
                      onFocus={() => setShowProjectDropdownForAssignment(true)}
                      onBlur={() => setTimeout(() => setShowProjectDropdownForAssignment(false), 200)}
                      onKeyDown={(e) => {
                        if (e.key === 'ArrowDown') {
                          e.preventDefault();
                          setActiveProjectIndexForAssignment((prev) => 
                            prev < filteredProjectsForSelection.length - 1 ? prev + 1 : prev
                          );
                        } else if (e.key === 'ArrowUp') {
                          e.preventDefault();
                          setActiveProjectIndexForAssignment((prev) => 
                            prev > 0 ? prev - 1 : prev
                          );
                        } else if (e.key === 'Enter') {
                          e.preventDefault();
                          if (filteredProjectsForSelection.length > 0) {
                            const proj = filteredProjectsForSelection[activeProjectIndexForAssignment];
                            setSelectedProjectId(String(proj.project_id));
                            setProjectSearchTextForAssignment(`[${proj.evaluatee_team || '부서없음'}] ${proj.evaluatee_name} ${proj.evaluatee_position || ''} (${proj.title})`);
                            setShowProjectDropdownForAssignment(false);
                          }
                        } else if (e.key === 'Escape') {
                          setShowProjectDropdownForAssignment(false);
                        }
                      }}
                      style={{ paddingRight: '30px' }}
                    />
                    {selectedProjectId && (
                      <button
                        onClick={() => {
                          setProjectSearchTextForAssignment('');
                          setSelectedProjectId('');
                          setSelectedEvaluators([]);
                          setExcelPasteText('');
                          setMappingPreview([]);
                        }}
                        style={{
                          position: 'absolute',
                          right: '10px',
                          border: 'none',
                          background: 'none',
                          fontSize: '16px',
                          cursor: 'pointer',
                          color: 'var(--text-muted)'
                        }}
                        type="button"
                      >
                        &times;
                      </button>
                    )}
                  </div>
                  
                  {showProjectDropdownForAssignment && projectSearchTextForAssignment.trim() !== '' && (
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      backgroundColor: '#ffffff',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      maxHeight: '220px',
                      overflowY: 'auto',
                      zIndex: 100,
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                    }}>
                      {filteredProjectsForSelection.length === 0 ? (
                        <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center' }}>
                          검색 결과가 없습니다.
                        </div>
                      ) : (
                        filteredProjectsForSelection.map((proj, index) => {
                          const isHighlighted = index === activeProjectIndexForAssignment;
                          return (
                            <div
                              key={proj.project_id}
                              onMouseDown={() => {
                                setSelectedProjectId(String(proj.project_id));
                                setProjectSearchTextForAssignment(`[${proj.evaluatee_team || '부서없음'}] ${proj.evaluatee_name} ${proj.evaluatee_position || ''} (${proj.title})`);
                                setShowProjectDropdownForAssignment(false);
                              }}
                              style={{
                                padding: '10px 12px',
                                cursor: 'pointer',
                                borderBottom: '1px solid #f1f5f9',
                                fontSize: '13px',
                                textAlign: 'left',
                                backgroundColor: isHighlighted ? '#eff6ff' : 'transparent',
                                color: isHighlighted ? 'var(--primary-color)' : 'var(--text-primary)'
                              }}
                              onMouseEnter={() => setActiveProjectIndexForAssignment(index)}
                            >
                              <strong>{proj.evaluatee_name}</strong> {proj.evaluatee_position} <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>({proj.evaluatee_team} | {proj.title})</span>
                              {isHighlighted && <span style={{ float: 'right', fontSize: '10px', color: 'var(--primary-color)', fontWeight: 'bold' }}>Enter로 선택</span>}
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>

                {/* 트랙 1: 직접 검색 추가 폼 */}
                {activeTrack === 'search' && (
                  <form onSubmit={handleCreateAssignment} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div className="input-group" style={{ position: 'relative' }}>
                      <label className="input-label" style={{ fontSize: '13px' }}>평가자 검색 및 추가</label>
                      <input
                        type="text"
                        className="input-field"
                        placeholder="성명, 부서 또는 사번으로 검색"
                        value={evaluatorSearchText}
                        onChange={(e) => {
                          setEvaluatorSearchText(e.target.value);
                          setShowEvaluatorDropdown(true);
                        }}
                        onFocus={() => setShowEvaluatorDropdown(true)}
                        onBlur={() => setTimeout(() => setShowEvaluatorDropdown(false), 200)}
                        onKeyDown={(e) => {
                          if (e.key === 'ArrowDown') {
                            e.preventDefault();
                            setActiveEvaluatorIndex((prev) => 
                              prev < filteredEvaluators.length - 1 ? prev + 1 : prev
                            );
                          } else if (e.key === 'ArrowUp') {
                            e.preventDefault();
                            setActiveEvaluatorIndex((prev) => 
                              prev > 0 ? prev - 1 : prev
                            );
                          } else if (e.key === 'Enter') {
                            e.preventDefault();
                            if (filteredEvaluators.length > 0) {
                              handleAddEvaluatorTag(filteredEvaluators[activeEvaluatorIndex]);
                              setEvaluatorSearchText('');
                              setShowEvaluatorDropdown(false);
                            }
                          } else if (e.key === 'Escape') {
                            setShowEvaluatorDropdown(false);
                          }
                        }}
                        disabled={!selectedProjectId}
                      />
                      {showEvaluatorDropdown && evaluatorSearchText.trim() !== '' && (
                        <div style={{
                          position: 'absolute',
                          top: '100%',
                          left: 0,
                          right: 0,
                          backgroundColor: '#ffffff',
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius-sm)',
                          maxHeight: '220px',
                          overflowY: 'auto',
                          zIndex: 100,
                          boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                        }}>
                          {filteredEvaluators.length === 0 ? (
                            <div style={{ padding: '12px', color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center' }}>
                              검색 결과가 없습니다.
                            </div>
                          ) : (
                            filteredEvaluators.map((emp, index) => {
                              const isHighlighted = index === activeEvaluatorIndex;
                              return (
                                <div
                                  key={emp.id}
                                  onMouseDown={() => {
                                    handleAddEvaluatorTag(emp);
                                    setEvaluatorSearchText('');
                                    setShowEvaluatorDropdown(false);
                                  }}
                                  style={{
                                    padding: '10px 12px',
                                    cursor: 'pointer',
                                    borderBottom: '1px solid #f1f5f9',
                                    fontSize: '13px',
                                    textAlign: 'left',
                                    backgroundColor: isHighlighted ? '#eff6ff' : 'transparent',
                                    color: isHighlighted ? 'var(--primary-color)' : 'var(--text-primary)'
                                  }}
                                  onMouseEnter={() => setActiveEvaluatorIndex(index)}
                                >
                                  <strong>{emp.name}</strong> {emp.position} <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>({emp.team_name} | {emp.emp_id})</span>
                                  {isHighlighted && <span style={{ float: 'right', fontSize: '10px', color: 'var(--primary-color)', fontWeight: 'bold' }}>Enter로 추가</span>}
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>

                    {/* 배정 대기 평가자 태그 리스트 */}
                    {selectedEvaluators.length > 0 && (
                      <div style={{ marginTop: '4px' }}>
                        <label className="input-label" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>배정 대기 목록 ({selectedEvaluators.length}명)</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', padding: '8px', border: '1px dashed var(--border-color)', borderRadius: 'var(--radius-sm)', backgroundColor: '#fcfcfc' }}>
                          {selectedEvaluators.map((emp) => (
                            <div
                              key={emp.id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                backgroundColor: 'var(--primary-light)',
                                color: 'var(--primary-color)',
                                padding: '5px 10px',
                                borderRadius: '20px',
                                fontSize: '12px',
                                fontWeight: '600'
                              }}
                            >
                              <span>{emp.name} ({emp.team_name || '부서없음'})</span>
                              <button
                                type="button"
                                onClick={() => handleRemoveEvaluatorTag(emp.id)}
                                style={{
                                  border: 'none',
                                  background: 'none',
                                  color: 'var(--primary-color)',
                                  marginLeft: '6px',
                                  cursor: 'pointer',
                                  fontSize: '14px',
                                  fontWeight: '700',
                                  padding: 0
                                }}
                              >
                                &times;
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <button className="btn btn-primary" type="submit" style={{ padding: '10px', fontSize: '14px' }}>
                      평가자 일괄 추가 배정
                    </button>
                  </form>
                )}

                {/* 트랙 2: 엑셀 복사 붙여넣기 일괄 추가 폼 */}
                {activeTrack === 'excel' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div className="input-group">
                      <label className="input-label" style={{ fontSize: '13px' }}>엑셀 조직도 이름 복사 붙여넣기</label>
                      <textarea
                        className="input-field"
                        rows="5"
                        placeholder="엑셀에서 복사한 이름들을 붙여넣으세요 (줄바꿈 등으로 구분)"
                        value={excelPasteText}
                        onChange={(e) => setExcelPasteText(e.target.value)}
                        disabled={!selectedProjectId}
                        style={{ resize: 'vertical', fontSize: '13px', lineHeight: '1.4', fontFamily: 'monospace' }}
                      />
                    </div>
                    <button
                      className="btn btn-secondary"
                      onClick={handleParseExcelList}
                      disabled={!selectedProjectId || !excelPasteText.trim()}
                      style={{ padding: '10px', fontSize: '14px' }}
                    >
                      사원 매핑 확인 (동명이인 자동 판별)
                    </button>

                    {/* 매핑 미리보기 영역 */}
                    {mappingPreview.length > 0 && (
                      <div style={{ marginTop: '10px' }}>
                        <label className="input-label" style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>매핑 결과 미리보기 ({mappingPreview.filter(p => p.status === 'success' || p.status === 'duplicate').length}명 매핑됨)</label>
                        <div style={{
                          maxHeight: '200px',
                          overflowY: 'auto',
                          border: '1px solid var(--border-color)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '8px',
                          backgroundColor: '#fafafa',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px'
                        }}>
                          {mappingPreview.map((preview, index) => {
                            const { inputName, matchedEmp, status, candidates } = preview;
                            return (
                              <div key={index} style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                padding: '6px 8px',
                                backgroundColor: '#ffffff',
                                border: '1px solid #f1f5f9',
                                borderRadius: '4px',
                                fontSize: '12px'
                              }}>
                                <span style={{ fontWeight: '600' }}>{inputName}</span>
                                
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  {/* 성공 매핑 */}
                                  {status === 'success' && matchedEmp && (
                                    <span style={{ color: '#059669', fontWeight: '500' }}>
                                      ✓ [{matchedEmp.team_name}] {matchedEmp.position} ({matchedEmp.emp_id})
                                    </span>
                                  )}

                                  {/* 동명이인 매핑 조율 */}
                                  {status === 'duplicate' && matchedEmp && (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                      <span style={{ color: '#d97706', fontWeight: 'bold', fontSize: '11px', marginRight: '4px' }}>동명이인:</span>
                                      <select
                                        value={matchedEmp.id}
                                        onChange={(e) => handleResolveDuplicate(inputName, parseInt(e.target.value, 10))}
                                        style={{
                                          padding: '2px 4px',
                                          fontSize: '11px',
                                          border: '1px solid var(--warning)',
                                          borderRadius: '4px',
                                          backgroundColor: '#fffbeb',
                                          color: '#b45309'
                                        }}
                                      >
                                        {candidates.map(c => (
                                          <option key={c.id} value={c.id}>
                                            [{c.team_name || '부서없음'}] {c.name} {c.position} ({c.emp_id})
                                          </option>
                                        ))}
                                      </select>
                                    </div>
                                  )}

                                  {/* 사원 없음 */}
                                  {status === 'not_found' && (
                                    <span style={{ color: 'var(--danger)', fontWeight: 'bold' }}>
                                      사원 없음
                                    </span>
                                  )}

                                  {/* 자기 자신 배정 제외 */}
                                  {status === 'self' && (
                                    <span style={{ color: 'var(--secondary-color)', fontStyle: 'italic' }}>
                                      본인 제외됨
                                    </span>
                                  )}

                                  {/* 이미 배정됨 */}
                                  {status === 'already_assigned' && matchedEmp && (
                                    <span style={{ color: 'var(--secondary-color)', textDecoration: 'line-through' }}>
                                      이미 배정됨 ([{matchedEmp.team_name}] {matchedEmp.position})
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        <button
                          className="btn btn-primary"
                          onClick={handleCreateAssignmentBulk}
                          style={{ padding: '10px', fontSize: '14px', marginTop: '10px' }}
                        >
                          엑셀 매핑 대상자 일괄 배정
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>

            </div>

            {/* 우측 영역 (배정 진행 현황 및 트리 영역) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              
              {/* 4. 현재 프로젝트 및 배정 현황 리스트 */}
              <div className="card" style={{ padding: '20px' }}>
                <h4 style={{ fontSize: '16px', fontWeight: '800', color: 'var(--text-secondary)', marginBottom: '16px', borderLeft: '4px solid var(--success)', paddingLeft: '8px' }}>
                  평가 프로젝트 및 배정 진행 현황 ({projects.length}개 프로젝트)
                </h4>

                {/* 다이내믹 실시간 필터 및 검색 컨트롤 */}
                {projects.length > 0 && (
                  <div style={{
                    display: 'flex',
                    gap: '12px',
                    marginBottom: '20px',
                    flexWrap: 'wrap'
                  }}>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="피평가자명, 부서, 사번 등으로 검색..."
                      value={projectSearchText}
                      onChange={(e) => setProjectSearchText(e.target.value)}
                      style={{ flex: 2, padding: '8px 12px', fontSize: '13px' }}
                    />
                    <select
                      className="input-field"
                      value={projectStatusFilter}
                      onChange={(e) => setProjectStatusFilter(e.target.value)}
                      style={{ flex: 1, padding: '8px 10px', fontSize: '13px', backgroundColor: 'var(--surface-color)' }}
                    >
                      <option value="all">전체 상태</option>
                      <option value="active">진행 중</option>
                      <option value="pending">진행 대기</option>
                      <option value="expired">기간 만료</option>
                    </select>
                    <button
                      onClick={() => { window.location.href = '/api/admin/results/export'; }}
                      style={{
                        border: '1px solid #10b981',
                        backgroundColor: '#ecfdf5',
                        color: '#047857',
                        fontSize: '13px',
                        fontWeight: '700',
                        padding: '8px 16px',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                    >
                      전체 결과 엑셀 다운로드
                    </button>
                  </div>
                )}

                {loading ? (
                  <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                    프로젝트 목록 로딩 중...
                  </div>
                ) : projects.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    생성된 평가 프로젝트가 없습니다. 왼쪽 폼에서 피평가자를 지정해 생성해 주세요.
                  </div>
                ) : filteredProjects.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    필터링 조건과 일치하는 평가 프로젝트가 존재하지 않습니다.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {filteredProjects.map((proj) => {
                      const projAssignments = assignments.filter((a) => a.project_id === proj.project_id);
                      const completedCount = projAssignments.filter((a) => a.status === 'completed').length;
                      const totalCount = projAssignments.length;
                      const projProgress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

                      // 평가 기간 상태 뱃지 계산
                      const todayStr = getTodayDateOnly();
                      let periodStatusText = '상시 진행';
                      let periodStatusBg = '#eff6ff';
                      let periodStatusColor = 'var(--primary-color)';

                      if (proj.start_date && proj.end_date) {
                        if (todayStr < proj.start_date) {
                          periodStatusText = '진행 대기';
                          periodStatusBg = '#f1f5f9';
                          periodStatusColor = '#64748b';
                        } else if (todayStr > proj.end_date) {
                          periodStatusText = '기간 만료';
                          periodStatusBg = '#fee2e2';
                          periodStatusColor = 'var(--danger)';
                        } else {
                          periodStatusText = '진행 중';
                          periodStatusBg = '#ecfdf5';
                          periodStatusColor = '#059669';
                        }
                      }

                      const isExpanded = expandedProjectIds.includes(proj.project_id);

                      return (
                        <div
                          key={proj.project_id}
                          style={{
                            border: '1px solid var(--border-color)',
                            borderRadius: 'var(--radius-md)',
                            backgroundColor: '#fbfcfd',
                            overflow: 'hidden',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
                            transition: 'all 0.2s ease'
                          }}
                        >
                          {/* 아코디언 헤더 바 (클릭으로 세부 설정 열기/닫기) */}
                          <div
                            onClick={() => toggleProjectExpand(proj.project_id)}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              padding: '14px 18px',
                              cursor: 'pointer',
                              backgroundColor: isExpanded ? 'var(--primary-light)' : '#ffffff',
                              borderBottom: isExpanded ? '1px solid var(--border-color)' : '1px solid transparent',
                              transition: 'all 0.2s ease',
                              userSelect: 'none'
                            }}
                          >
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, textAlign: 'left' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)' }}>
                                  {proj.evaluatee_name} {proj.evaluatee_position || ''}
                                </span>
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                                  ({proj.evaluatee_team || '부서없음'} | 사번: {proj.evaluatee_emp_id})
                                </span>
                                <span style={{
                                  fontSize: '10px',
                                  fontWeight: '700',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  backgroundColor: periodStatusBg,
                                  color: periodStatusColor
                                }}>
                                  {periodStatusText}
                                </span>
                              </div>
                              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                                {proj.start_date && proj.end_date ? `${proj.start_date} ~ ${proj.end_date}` : '상시 진행'}
                              </span>
                            </div>

                            {/* 진행 현황 요약 게이지 바 */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginRight: '16px' }}>
                              {totalCount > 0 ? (
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                                  <span style={{ fontSize: '11px', fontWeight: '700', color: 'var(--text-secondary)' }}>
                                    {completedCount}/{totalCount}명 완료 ({projProgress}%)
                                  </span>
                                  <div style={{
                                    width: '80px',
                                    height: '4px',
                                    backgroundColor: '#e2e8f0',
                                    borderRadius: '2px',
                                    overflow: 'hidden'
                                  }}>
                                    <div style={{
                                      width: `${projProgress}%`,
                                      height: '100%',
                                      backgroundColor: 'var(--success)'
                                    }}></div>
                                  </div>
                                </div>
                              ) : (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                                  배정 인원 없음
                                </span>
                              )}
                            </div>

                            {/* 아코디언 토글 화살표 */}
                            <span style={{
                              fontSize: '12px',
                              color: 'var(--text-secondary)',
                              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                              transition: 'transform 0.2s ease',
                              display: 'inline-block'
                            }}>
                              ▼
                            </span>
                          </div>

                          {/* 아코디언 바디 (세부 정보 및 관리 패널) */}
                          {isExpanded && (
                            <div style={{
                              padding: '18px',
                              backgroundColor: '#fcfdfe',
                              borderTop: '1px solid #f1f5f9',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '16px'
                            }}>
                              {/* 프로젝트 세부 정보 및 기간 수정 */}
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', paddingBottom: '12px', borderBottom: '1px solid #f1f5f9' }}>
                                <div style={{ textAlign: 'left' }}>
                                  {editingProjectId === proj.project_id ? (
                                    <div style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '8px',
                                      flexWrap: 'wrap',
                                      backgroundColor: '#f8fafc',
                                      padding: '8px',
                                      borderRadius: '6px',
                                      border: '1px solid var(--border-color)'
                                    }}>
                                      <input
                                        type="date"
                                        className="input-field"
                                        value={editStartDate}
                                        onChange={(e) => setEditStartDate(e.target.value)}
                                        style={{ padding: '4px 8px', fontSize: '12px', width: 'auto' }}
                                      />
                                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>~</span>
                                      <input
                                        type="date"
                                        className="input-field"
                                        value={editEndDate}
                                        onChange={(e) => setEditEndDate(e.target.value)}
                                        style={{ padding: '4px 8px', fontSize: '12px', width: 'auto' }}
                                      />
                                      <button
                                        onClick={() => handleSavePeriod(proj.project_id)}
                                        style={{
                                          border: 'none',
                                          backgroundColor: 'var(--primary-color)',
                                          color: '#ffffff',
                                          fontSize: '11px',
                                          fontWeight: '600',
                                          padding: '4px 8px',
                                          borderRadius: '4px',
                                          cursor: 'pointer'
                                        }}
                                      >
                                        저장
                                      </button>
                                      <button
                                        onClick={handleCancelEditPeriod}
                                        style={{
                                          border: '1px solid var(--border-color)',
                                          backgroundColor: '#ffffff',
                                          color: 'var(--text-secondary)',
                                          fontSize: '11px',
                                          fontWeight: '600',
                                          padding: '4px 8px',
                                          borderRadius: '4px',
                                          cursor: 'pointer'
                                        }}
                                      >
                                        취소
                                      </button>
                                    </div>
                                  ) : (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                      <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: '600' }}>
                                        프로젝트 전체 타이틀: {proj.title}
                                      </span>
                                      <button
                                        onClick={() => handleStartEditPeriod(proj)}
                                        style={{
                                          border: 'none',
                                          background: 'none',
                                          color: 'var(--primary-color)',
                                          fontSize: '11px',
                                          fontWeight: '600',
                                          cursor: 'pointer',
                                          textDecoration: 'underline',
                                          padding: 0
                                        }}
                                      >
                                        기간 수정
                                      </button>
                                    </div>
                                  )}
                                </div>

                                <div style={{ display: 'flex', gap: '8px' }}>
                                  <button
                                    onClick={() => handleCopyEvaluatorPhones(proj.project_id)}
                                    style={{
                                      border: '1px solid var(--primary-color)',
                                      backgroundColor: 'var(--primary-light)',
                                      color: 'var(--primary-color)',
                                      fontSize: '11px',
                                      fontWeight: '600',
                                      padding: '4px 10px',
                                      borderRadius: '4px',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    평가자 연락처 일괄 복사
                                  </button>
                                  <button
                                    onClick={() => handleDeleteProject(proj.project_id)}
                                    style={{
                                      border: 'none',
                                      backgroundColor: '#fee2e2',
                                      color: 'var(--danger)',
                                      fontSize: '11px',
                                      fontWeight: '600',
                                      padding: '4px 10px',
                                      borderRadius: '4px',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    프로젝트 삭제
                                  </button>
                                </div>
                              </div>

                              {/* 배정된 평가자 세부 관리 */}
                              <div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                  <h5 style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-secondary)', margin: 0, textAlign: 'left' }}>
                                    배정된 평가자 목록 및 개별 상태 제어
                                  </h5>
                                  {projAssignments.some(item => item.status === 'completed') && (
                                    <button
                                      onClick={() => handleBulkPDFDownload(proj.project_id, proj.title)}
                                      style={{
                                        border: '1px solid var(--primary-color)',
                                        backgroundColor: 'var(--primary-color)',
                                        color: '#ffffff',
                                        fontSize: '11px',
                                        fontWeight: '700',
                                        padding: '4px 10px',
                                        borderRadius: '4px',
                                        cursor: 'pointer'
                                      }}
                                    >
                                      완료확인서 일괄 PDF 다운로드
                                    </button>
                                  )}
                                </div>

                                {projAssignments.length === 0 ? (
                                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic', margin: '4px 0', textAlign: 'left' }}>
                                    등록된 평가자가 없습니다. 왼쪽 배정 폼을 이용해 평가자를 배정해 주세요.
                                  </p>
                                ) : (
                                  <div style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                                    gap: '8px'
                                  }}>
                                    {projAssignments.map((item) => {
                                      const isCompleted = item.status === 'completed';
                                      return (
                                        <div
                                          key={item.assignment_id}
                                          style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            padding: '8px 12px',
                                            backgroundColor: isCompleted ? '#ecfdf5' : '#ffffff',
                                            borderRadius: '6px',
                                            border: isCompleted ? '1px solid #a7f3d0' : '1px solid var(--border-color)',
                                            fontSize: '12px'
                                          }}
                                        >
                                          <div style={{ textAlign: 'left' }}>
                                            <strong>{item.evaluator_name}</strong> {item.evaluator_position}
                                            {item.evaluator_phone && (
                                              <span style={{ color: 'var(--text-secondary)', fontSize: '10px', marginLeft: '6px' }}>
                                                ({item.evaluator_phone})
                                              </span>
                                            )}
                                            <div style={{ fontSize: '10px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                                              {item.evaluator_team}
                                            </div>
                                          </div>
                                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                            <select
                                              value={item.status}
                                              onChange={(e) => handleStatusChange(item.assignment_id, e.target.value)}
                                              style={{
                                                fontSize: '11px',
                                                fontWeight: '700',
                                                padding: '2px 4px',
                                                borderRadius: '6px',
                                                border: '1px solid',
                                                borderColor: item.status === 'completed'
                                                  ? '#a7f3d0'
                                                  : item.status === 'saved'
                                                  ? '#fde68a'
                                                  : '#cbd5e1',
                                                backgroundColor: item.status === 'completed'
                                                  ? '#ecfdf5'
                                                  : item.status === 'saved'
                                                  ? '#fffbeb'
                                                  : '#f8fafc',
                                                color: item.status === 'completed'
                                                  ? '#065f46'
                                                  : item.status === 'saved'
                                                  ? '#d97706'
                                                  : '#475569',
                                                cursor: 'pointer',
                                                outline: 'none'
                                              }}
                                            >
                                              <option value="pending">대기</option>
                                              <option value="saved">임시 저장</option>
                                              <option value="completed">완료</option>
                                            </select>
                                            {isCompleted && (
                                              <button
                                                onClick={() => handlePrintEvaluation(item.assignment_id)}
                                                style={{
                                                  border: '1px solid var(--primary-color)',
                                                  backgroundColor: '#ffffff',
                                                  color: 'var(--primary-color)',
                                                  fontSize: '11px',
                                                  fontWeight: '700',
                                                  padding: '2px 6px',
                                                  borderRadius: '4px',
                                                  cursor: 'pointer'
                                                }}
                                              >
                                                인쇄/PDF
                                              </button>
                                            )}
                                            <button
                                              onClick={() => handleDeleteAssignment(item.assignment_id)}
                                              style={{
                                                border: 'none',
                                                background: 'none',
                                                color: 'var(--danger)',
                                                fontWeight: 'bold',
                                                cursor: 'pointer',
                                                padding: '2px'
                                              }}
                                            >
                                              &times;
                                            </button>
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

            </div>

          </div>
        )}


        {activeTab === 'questions' && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(360px, 400px) 1fr',
            gap: '24px',
            alignItems: 'start'
          }}>
            {/* 1. 신규 평가문항 추가 카드 */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '16px', borderLeft: '4px solid var(--primary-color)', paddingLeft: '8px' }}>
                신규 평가 문항 등록
              </h3>
              <form onSubmit={handleCreateQuestion} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div className="input-group">
                  <label className="input-label" style={{ fontSize: '13px' }}>평가 종류</label>
                  <select
                    className="input-field"
                    value={questionEvaluationType}
                    onChange={(e) => setQuestionEvaluationType(e.target.value)}
                    style={{ backgroundColor: 'var(--surface-color)', padding: '10px' }}
                  >
                    {evaluationTypes.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-label" style={{ fontSize: '13px' }}>문항 제목</label>
                  <input
                    type="text"
                    className="input-field"
                    placeholder="예: 협업 능력, 직무 성과, 종합의견 등"
                    value={questionCategory}
                    onChange={(e) => setQuestionCategory(e.target.value)}
                    required
                  />
                </div>
                <div className="input-group">
                  <label className="input-label" style={{ fontSize: '13px' }}>문항 종류</label>
                  <select
                    className="input-field"
                    value={questionIsEssay}
                    onChange={(e) => setQuestionIsEssay(parseInt(e.target.value, 10))}
                    style={{ backgroundColor: 'var(--surface-color)', padding: '10px' }}
                  >
                    <option value={0}>객관식 (5점 척도)</option>
                    <option value={1}>주관식 (서술형 답변)</option>
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-label" style={{ fontSize: '13px' }}>문항 설명 (주 설명)</label>
                  <textarea
                    className="input-field"
                    rows="3"
                    placeholder="임직원이 동료를 평가할 때 참고할 주 설명 문구를 입력하세요."
                    value={questionText}
                    onChange={(e) => setQuestionText(e.target.value)}
                    style={{ resize: 'vertical', fontSize: '13px', lineHeight: '1.4' }}
                    required
                  />
                </div>
                <div className="input-group">
                  <label className="input-label" style={{ fontSize: '13px' }}>보조 설명 (선택)</label>
                  <textarea
                    className="input-field"
                    rows="2"
                    placeholder="폰트가 작게 표시되어 강조를 덜고자 하는 보조 상세 설명이나 예시를 입력하세요."
                    value={questionSubText}
                    onChange={(e) => setQuestionSubText(e.target.value)}
                    style={{ resize: 'vertical', fontSize: '13px', lineHeight: '1.4' }}
                  />
                </div>
                <button className="btn btn-primary" type="submit" style={{ padding: '10px', fontSize: '14px' }}>
                  문항 추가 등록
                </button>
              </form>
            </div>

            {/* 2. 기존 평가 문항 설정 및 편집 카드 */}
            <div className="card" style={{ padding: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', borderLeft: '4px solid var(--success)', paddingLeft: '8px', margin: 0 }}>
                  현재 평가 문항 목록
                </h3>
                {/* 평가 종류 분류 필터 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)', fontWeight: '600' }}>평가 종류 필터:</span>
                  <select
                    className="input-field"
                    value={questionFilterType}
                    onChange={(e) => setQuestionFilterType(e.target.value)}
                    style={{ padding: '6px 12px', fontSize: '13px', width: 'auto', backgroundColor: '#ffffff' }}
                  >
                    <option value="전체">전체 보기</option>
                    {evaluationTypes.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border-color)', textAlign: 'left', backgroundColor: '#f8fafc' }}>
                      <th style={{ padding: '10px', width: '70px', color: 'var(--text-secondary)', textAlign: 'center' }}>순서</th>
                      <th style={{ padding: '10px', width: '110px', color: 'var(--text-secondary)' }}>평가 종류</th>
                      <th style={{ padding: '10px', width: '90px', color: 'var(--text-secondary)' }}>문항 제목</th>
                      <th style={{ padding: '10px', width: '90px', color: 'var(--text-secondary)' }}>유형</th>
                      <th style={{ padding: '10px', color: 'var(--text-secondary)' }}>문항 설명</th>
                      <th style={{ padding: '10px', width: '80px', color: 'var(--text-secondary)', textAlign: 'center' }}>상태</th>
                      <th style={{ padding: '10px', width: '120px', color: 'var(--text-secondary)', textAlign: 'center' }}>작업</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(() => {
                      const filteredList = questions.filter(q => {
                        if (questionFilterType === '전체') return true;
                        return (q.evaluation_type || '동료사원 평가') === questionFilterType;
                      });

                      if (filteredList.length === 0) {
                        return (
                          <tr>
                            <td colSpan="7" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                              해당 종류의 평가 문항이 없습니다.
                            </td>
                          </tr>
                        );
                      }

                      return filteredList.map((q) => {
                        const realIndex = questions.indexOf(q);
                        const isEditing = editingQuestionId === q.id;
                        return (
                          <tr key={q.id} style={{ borderBottom: '1px solid var(--border-color)', opacity: q.is_active ? 1 : 0.6 }}>
                            {isEditing ? (
                              <>
                                <td style={{ padding: '8px', textAlign: 'center' }}>-</td>
                                <td style={{ padding: '8px 4px' }}>
                                  <select
                                    className="input-field"
                                    value={editQuestionEvaluationType}
                                    onChange={(e) => setEditQuestionEvaluationType(e.target.value)}
                                    style={{ padding: '6px', fontSize: '12px', backgroundColor: '#fff' }}
                                  >
                                    {evaluationTypes.map((t) => (
                                      <option key={t} value={t}>{t}</option>
                                    ))}
                                  </select>
                                </td>
                                <td style={{ padding: '8px 4px' }}>
                                  <input
                                    type="text"
                                    className="input-field"
                                    value={editQuestionCategory}
                                    onChange={(e) => setEditQuestionCategory(e.target.value)}
                                    style={{ padding: '6px', fontSize: '12px' }}
                                  />
                                </td>
                                <td style={{ padding: '8px 4px' }}>
                                  <select
                                    className="input-field"
                                    value={editQuestionIsEssay}
                                    onChange={(e) => setEditQuestionIsEssay(parseInt(e.target.value, 10))}
                                    style={{ padding: '6px', fontSize: '12px', backgroundColor: '#fff' }}
                                  >
                                    <option value={0}>객관식</option>
                                    <option value={1}>주관식</option>
                                  </select>
                                </td>
                                <td style={{ padding: '8px 4px' }}>
                                  <textarea
                                    className="input-field"
                                    placeholder="주 설명"
                                    value={editQuestionText}
                                    onChange={(e) => setEditQuestionText(e.target.value)}
                                    style={{ padding: '6px', fontSize: '12px', resize: 'vertical', width: '100%', minHeight: '40px', marginBottom: '4px' }}
                                  />
                                  <textarea
                                    className="input-field"
                                    placeholder="보조 설명"
                                    value={editQuestionSubText}
                                    onChange={(e) => setEditQuestionSubText(e.target.value)}
                                    style={{ padding: '6px', fontSize: '11px', resize: 'vertical', width: '100%', minHeight: '30px' }}
                                  />
                                </td>
                                <td style={{ padding: '8px', textAlign: 'center' }}>
                                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>수정 중</span>
                                </td>
                                <td style={{ padding: '8px', textAlign: 'center' }}>
                                  <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                                    <button
                                      onClick={() => handleSaveQuestion(q.id)}
                                      style={{ border: 'none', backgroundColor: '#10b981', color: '#fff', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}
                                    >
                                      저장
                                    </button>
                                    <button
                                      onClick={() => setEditingQuestionId(null)}
                                      style={{ border: '1px solid var(--border-color)', backgroundColor: '#fff', color: 'var(--text-secondary)', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}
                                    >
                                      취소
                                    </button>
                                  </div>
                                </td>
                              </>
                            ) : (
                              <>
                                <td style={{ padding: '8px', textAlign: 'center' }}>
                                  <div style={{ display: 'flex', gap: '4px', justifyContent: 'center' }}>
                                    <button
                                      type="button"
                                      onClick={() => handleMoveQuestion(realIndex, 'up')}
                                      disabled={realIndex === 0}
                                      style={{
                                        border: '1px solid var(--border-color)',
                                        backgroundColor: '#ffffff',
                                        color: realIndex === 0 ? '#cbd5e1' : 'var(--text-primary)',
                                        padding: '2px 6px',
                                        borderRadius: '4px',
                                        cursor: realIndex === 0 ? 'not-allowed' : 'pointer',
                                        fontSize: '11px',
                                        fontWeight: 'bold'
                                      }}
                                    >
                                      ↑
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleMoveQuestion(realIndex, 'down')}
                                      disabled={realIndex === questions.length - 1}
                                      style={{
                                        border: '1px solid var(--border-color)',
                                        backgroundColor: '#ffffff',
                                        color: realIndex === questions.length - 1 ? '#cbd5e1' : 'var(--text-primary)',
                                        padding: '2px 6px',
                                        borderRadius: '4px',
                                        cursor: realIndex === questions.length - 1 ? 'not-allowed' : 'pointer',
                                        fontSize: '11px',
                                        fontWeight: 'bold'
                                      }}
                                    >
                                      ↓
                                    </button>
                                  </div>
                                </td>
                                <td style={{ padding: '12px 10px', fontWeight: '700', color: 'var(--primary-color)' }}>{q.evaluation_type || '동료사원 평가'}</td>
                                <td style={{ padding: '12px 10px', fontWeight: '600' }}>{q.category}</td>
                                <td style={{ padding: '12px 10px' }}>
                                  <span style={{
                                    padding: '2px 6px',
                                    borderRadius: '10px',
                                    fontSize: '11px',
                                    fontWeight: 'bold',
                                    backgroundColor: q.is_essay ? '#fff3cd' : '#e2e3e5',
                                    color: q.is_essay ? '#856404' : '#383d41'
                                  }}>
                                    {q.is_essay ? '주관식' : '객관식'}
                                  </span>
                                </td>
                                <td style={{ padding: '12px 10px', lineHeight: '1.4' }}>
                                  <div style={{ whiteSpace: 'pre-wrap', fontWeight: '500' }}>{q.question_text}</div>
                                  {q.question_sub_text && (
                                    <div style={{
                                      fontSize: '11px',
                                      color: '#64748b',
                                      marginTop: '4px',
                                      whiteSpace: 'pre-wrap',
                                      lineHeight: '1.4'
                                    }}>
                                      {q.question_sub_text}
                                    </div>
                                  )}
                                </td>
                                <td style={{ padding: '12px 10px', textAlign: 'center' }}>
                                  <span style={{
                                    fontSize: '11px',
                                    fontWeight: '700',
                                    color: q.is_active ? '#065f46' : '#991b1b',
                                    backgroundColor: q.is_active ? '#d1fae5' : '#fee2e2',
                                    padding: '2px 6px',
                                    borderRadius: '8px'
                                  }}>
                                    {q.is_active ? '사용중' : '비활성'}
                                  </span>
                                </td>
                                <td style={{ padding: '12px 10px', textAlign: 'center' }}>
                                  <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                                    <button
                                      onClick={() => handleStartEditQuestion(q)}
                                      style={{ border: 'none', backgroundColor: 'var(--primary-light)', color: 'var(--primary-color)', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}
                                    >
                                      수정
                                    </button>
                                    {q.is_active ? (
                                      <button
                                        onClick={() => handleDeleteQuestion(q.id)}
                                        style={{ border: 'none', backgroundColor: '#fee2e2', color: 'var(--danger)', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}
                                      >
                                        삭제
                                      </button>
                                    ) : (
                                      <button
                                        onClick={() => handleActivateQuestion(q.id)}
                                        style={{ border: 'none', backgroundColor: '#e0f2fe', color: '#0369a1', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}
                                      >
                                        복구
                                      </button>
                                    )}
                                  </div>
                                </td>
                              </>
                            )}
                          </tr>
                        );
                      });
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
      {pdfLoading && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 9999,
        }}>
          <div className="card" style={{
            padding: '30px 40px',
            maxWidth: '400px',
            width: '100%',
            textAlign: 'center',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            borderRadius: '12px',
            backgroundColor: '#ffffff',
            border: 'none'
          }}>
            <div style={{
              margin: '0 auto 16px auto',
              border: '4px solid #f3f3f3',
              borderTop: '4px solid var(--primary-color)',
              borderRadius: '50%',
              width: '40px',
              height: '40px',
              animation: 'spin 1s linear infinite'
            }} />
            <style>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
            <h4 style={{ fontSize: '16px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '8px' }}>
              PDF 문서 생성 중
            </h4>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>
              {pdfLoadingMsg}
            </p>
            <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '8px', fontStyle: 'italic' }}>
              잠시만 기다려 주세요. 이 작업은 다소 시간이 걸릴 수 있습니다.
            </p>
          </div>
        </div>
      )}
    </>
  );
}

export default AdminDashboard;
