(function () {
  const API_BASE = (window.API_BASE || '').replace(/\/$/, '');
  const api = (path) => `${API_BASE}${path}`;

  const nlInput = document.getElementById('nl-input');
  const btnGenerate = document.getElementById('btn-generate');
  const nlStatus = document.getElementById('nl-status');
  const sqlEditor = document.getElementById('sql-editor');
  const btnRun = document.getElementById('btn-run');
  const sqlStatus = document.getElementById('sql-status');
  const resultsPlaceholder = document.getElementById('results-placeholder');
  const resultsTableWrap = document.getElementById('results-table-wrap');
  const resultsTable = document.getElementById('results-table');
  const resultsError = document.getElementById('results-error');
  const backendStatus = document.getElementById('backend-status');

  function setStatus(el, text, isError) {
    el.textContent = text || '';
    el.hidden = !text;
    el.className = 'status' + (isError ? ' error' : '');
  }

  function showResults(columns, rows) {
    resultsError.hidden = true;
    resultsPlaceholder.hidden = true;
    resultsTableWrap.hidden = false;
    resultsTable.innerHTML = '';
    const thead = document.createElement('thead');
    const trHead = document.createElement('tr');
    columns.forEach(function (col) {
      const th = document.createElement('th');
      th.textContent = col;
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    resultsTable.appendChild(thead);
    const tbody = document.createElement('tbody');
    rows.forEach(function (row) {
      const tr = document.createElement('tr');
      row.forEach(function (cell) {
        const td = document.createElement('td');
        td.textContent = cell != null ? String(cell) : '';
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    resultsTable.appendChild(tbody);
  }

  function showResultsError(message) {
    resultsTableWrap.hidden = true;
    resultsPlaceholder.hidden = true;
    resultsError.hidden = false;
    resultsError.textContent = message;
  }

  function showResultsPlaceholder() {
    resultsTableWrap.hidden = true;
    resultsError.hidden = true;
    resultsPlaceholder.hidden = false;
  }

  // Health check and backend status
  function checkBackend() {
    fetch(api('/api/health'), { method: 'GET' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        backendStatus.textContent = data ? 'Backend connected' : 'Backend not reachable (set API_BASE in config.js if on GitHub Pages)';
        backendStatus.className = 'backend-status ' + (data ? 'ok' : 'warn');
      })
      .catch(function () {
        backendStatus.textContent = 'Backend not reachable';
        backendStatus.className = 'backend-status warn';
      });
  }
  checkBackend();

  // Generate SQL from natural language
  btnGenerate.addEventListener('click', function () {
    const question = (nlInput.value || '').trim();
    if (!question) {
      setStatus(nlStatus, 'Enter a question.', true);
      return;
    }
    setStatus(nlStatus, 'Generating…');
    btnGenerate.disabled = true;
    fetch(api('/api/nl-to-sql'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question }),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data }; }); })
      .then(function (_ref) {
        var ok = _ref.ok, data = _ref.data;
        if (ok && data.sql) {
          sqlEditor.value = data.sql;
          setStatus(nlStatus, 'SQL generated. Edit if needed and click Run.');
        } else {
          setStatus(nlStatus, data.error || 'Failed to generate SQL', true);
        }
      })
      .catch(function (err) {
        setStatus(nlStatus, 'Request failed: ' + (err.message || 'network error'), true);
      })
      .finally(function () { btnGenerate.disabled = false; });
  });

  // Run SQL
  btnRun.addEventListener('click', function () {
    const sql = (sqlEditor.value || '').trim();
    if (!sql) {
      setStatus(sqlStatus, 'Enter a SQL query.', true);
      return;
    }
    setStatus(sqlStatus, 'Running…');
    btnRun.disabled = true;
    fetch(api('/api/run-sql'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql: sql }),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, status: r.status, data }; }); })
      .then(function (_ref2) {
        var ok = _ref2.ok, status = _ref2.status, data = _ref2.data;
        if (ok && data.columns && Array.isArray(data.rows)) {
          showResults(data.columns, data.rows);
          setStatus(sqlStatus, 'Rows: ' + data.rows.length);
        } else {
          showResultsError(data.error || 'Query failed');
          setStatus(sqlStatus, data.error || 'Error', true);
        }
      })
      .catch(function (err) {
        showResultsError(err.message || 'Request failed');
        setStatus(sqlStatus, 'Request failed', true);
      })
      .finally(function () { btnRun.disabled = false; });
  });
})();
