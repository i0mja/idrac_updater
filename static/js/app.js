// SPDX-License-Identifier: Apache-2.0
const main = document.getElementById('main');
const sidebar = document.getElementById('sidebar');
document.getElementById('toggle-sidebar').addEventListener('click', () => {
  sidebar.classList.toggle('show');
});

function parseAndSwap(html, url) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const newMain = doc.getElementById('main');
  if (newMain) {
    main.innerHTML = newMain.innerHTML;
    initPage(url);
  }
}

function navigate(url, push = true) {
  fetch(url, { headers: { 'X-Requested-With': 'fetch' } })
    .then(r => r.text())
    .then(html => {
      parseAndSwap(html, url);
      if (push) history.pushState({}, '', url);
    });
}

window.addEventListener('popstate', () => navigate(location.pathname, false));

document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    navigate(a.getAttribute('href'));
  });
});

function initDashboard() {
  fetch('/api/v1/metrics/summary')
    .then(r => r.json())
    .then(s => {
      document.querySelector('#stat-servers .value').textContent = s.servers;
      document.querySelector('#stat-updates .value').textContent = s.pending;
      document.querySelector('#stat-jobs .value').textContent = s.jobs;
      document.querySelector('#stat-protected .value').textContent = s.protected;
    });
  fetch('/api/v1/activity?limit=20')
    .then(r => r.json())
    .then(items => {
      const feed = document.querySelector('#activity-feed .feed');
      feed.innerHTML = '';
      items.forEach(it => {
        const li = document.createElement('li');
        li.textContent = it.message;
        feed.appendChild(li);
      });
    });
  fetch('/api/v1/compliance')
    .then(r => r.json())
    .then(c => {
      const ctx = document.getElementById('compliance-chart');
      // eslint-disable-next-line no-undef
      new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Compliant', 'Drifted'],
          datasets: [{
            data: [c.compliant, c.drifted],
            backgroundColor: [getComputedStyle(document.documentElement).getPropertyValue('--primary'), '#555']
          }]
        },
        options: { plugins: { legend: { position: 'bottom' } } }
      });
    });
}

function loadHosts() {
  fetch('/api/v1/hosts')
    .then(r => r.json())
    .then(hosts => {
      const tbody = document.querySelector('#hosts-table tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
      hosts.forEach(h => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${h.hostname}</td><td>${h.ip}</td><td>${h.cluster || ''}</td><td>${h.host_policy || ''}</td><td>${h.status}</td>`;
        tbody.appendChild(tr);
      });
    });
}

function initPage(url) {
  if (url.startsWith('/dashboard')) initDashboard();
  if (url.startsWith('/hosts')) loadHosts();
}

initPage(location.pathname);
