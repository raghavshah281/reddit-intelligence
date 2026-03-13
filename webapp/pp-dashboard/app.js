(function () {
  'use strict';

  let issues = [];
  let sortKey = 'priority_score';
  let sortDir = -1;
  let expandedId = null;

  const tableBody = document.getElementById('table-body');
  const tableWrap = document.getElementById('table-wrap');
  const loadStatus = document.getElementById('load-status');
  const detailsRow = document.getElementById('details-row');
  const detailsContent = document.getElementById('details-content');

  function fetchData() {
    loadStatus.textContent = 'Loading insights…';
    loadStatus.classList.remove('error');
    fetch('insights.json')
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        if (!Array.isArray(data)) data = [];
        issues = data;
        loadStatus.textContent = issues.length + ' issue(s)';
        render();
        tableWrap.hidden = false;
      })
      .catch(function (err) {
        loadStatus.textContent = 'Failed to load insights: ' + err.message;
        loadStatus.classList.add('error');
      });
  }

  function priorityClass(score) {
    if (score >= 70) return 'priority-high';
    if (score >= 40) return 'priority-medium';
    return 'priority-low';
  }

  function escapeHtml(s) {
    if (s == null) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function formatLinks(links) {
    if (!links || !links.length) return '—';
    return links.slice(0, 3).map(function (url) {
      return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">Reddit</a>';
    }).join(', ');
  }

  function renderRow(issue, index) {
    var tr = document.createElement('tr');
    tr.dataset.issueId = issue.issue_id;
    tr.className = priorityClass(issue.priority_score);

    var cells = [
      issue.priority_score != null ? Number(issue.priority_score).toFixed(1) : '—',
      escapeHtml(issue.issue_title || '—'),
      escapeHtml(issue.category || '—'),
      escapeHtml(issue.sentiment || '—'),
      issue.unique_users != null ? String(issue.unique_users) : '—',
      issue.engagement_score != null ? Number(issue.engagement_score).toFixed(0) : '—',
      issue.total_mentions != null ? String(issue.total_mentions) : '—',
      escapeHtml(issue.last_seen_date || '—'),
      issue.responded_by_clickup ? 'Yes' : 'No',
      formatLinks(issue.source_links),
    ];

    cells.forEach(function (html) {
      var td = document.createElement('td');
      td.innerHTML = html;
      tr.appendChild(td);
    });

    var expandTd = document.createElement('td');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'expand-btn';
    btn.textContent = 'Expand';
    btn.setAttribute('aria-expanded', expandedId === issue.issue_id ? 'true' : 'false');
    btn.onclick = function () {
      toggleExpand(issue.issue_id);
    };
    expandTd.appendChild(btn);
    tr.appendChild(expandTd);

    return tr;
  }

  function renderDetails(issue) {
    var parts = [];
    if (issue.summary) {
      parts.push('<p><strong>Summary</strong>: ' + escapeHtml(issue.summary) + '</p>');
    }
    if (issue.root_cause_hypothesis) {
      parts.push('<p><strong>Root cause</strong>: ' + escapeHtml(issue.root_cause_hypothesis) + '</p>');
    }
    if (issue.affected_plan_or_feature) {
      parts.push('<p><strong>Affected</strong>: ' + escapeHtml(issue.affected_plan_or_feature) + '</p>');
    }
    if (issue.example_quotes && issue.example_quotes.length) {
      parts.push('<p><strong>Example quotes</strong>:<ul>');
      issue.example_quotes.forEach(function (q) {
        parts.push('<li>' + escapeHtml(q) + '</li>');
      });
      parts.push('</ul></p>');
    }
    if (issue.source_links && issue.source_links.length) {
      parts.push('<p><strong>Sources</strong>: ');
      issue.source_links.forEach(function (url) {
        parts.push('<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">' + escapeHtml(url) + '</a> ');
      });
      parts.push('</p>');
    }
    return parts.join('');
  }

  function toggleExpand(issueId) {
    if (expandedId === issueId) {
      expandedId = null;
      detailsRow.hidden = true;
    } else {
      expandedId = issueId;
      var issue = issues.find(function (i) { return i.issue_id === issueId; });
      if (issue) {
        detailsContent.innerHTML = renderDetails(issue);
        detailsRow.hidden = false;
      }
    }
    var btns = document.querySelectorAll('.expand-btn');
    btns.forEach(function (btn) {
      var row = btn.closest('tr');
      btn.setAttribute('aria-expanded', row && row.dataset.issueId === expandedId ? 'true' : 'false');
      btn.textContent = row && row.dataset.issueId === expandedId ? 'Collapse' : 'Expand';
    });
  }

  function render() {
    var sorted = issues.slice().sort(function (a, b) {
      var va = a[sortKey];
      var vb = b[sortKey];
      if (sortKey === 'priority_score' || sortKey === 'engagement_score' || sortKey === 'total_mentions' || sortKey === 'unique_users') {
        va = Number(va);
        vb = Number(vb);
        return sortDir * (va - vb);
      }
      if (sortKey === 'responded_by_clickup') {
        va = va ? 1 : 0;
        vb = vb ? 1 : 0;
        return sortDir * (va - vb);
      }
      va = String(va || '');
      vb = String(vb || '');
      return sortDir * va.localeCompare(vb);
    });

    tableBody.innerHTML = '';
    sorted.forEach(function (issue) {
      tableBody.appendChild(renderRow(issue));
    });
  }

  function initSort() {
    document.querySelectorAll('#insights-table th.sortable').forEach(function (th) {
      th.addEventListener('click', function () {
        var key = th.dataset.sort;
        if (sortKey === key) sortDir = -sortDir;
        else { sortKey = key; sortDir = -1; }
        render();
      });
    });
  }

  fetchData();
  initSort();
})();
