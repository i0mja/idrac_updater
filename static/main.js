// simple flash message auto-dismiss
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.flashes li').forEach(li => li.style.display = 'none');
  }, 4000);

  const table = document.getElementById('hosts-table');
  if (table) {
    fetch('/api/v1/hosts')
      .then(resp => resp.json())
      .then(data => {
        const tbody = table.querySelector('tbody');
        tbody.innerHTML = '';
        data.forEach(h => {
          const tr = document.createElement('tr');
          tr.innerHTML = `<td>${h.hostname}</td><td>${h.ip}</td><td>${h.cluster || ''}</td><td>${h.host_policy || ''}</td><td>${h.status}</td>`;
          tbody.appendChild(tr);
        });
      });
  }
});
