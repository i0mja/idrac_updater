// simple flash message auto-dismiss
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    document.querySelectorAll('.flashes li').forEach(li => li.style.display = 'none');
  }, 4000);
});
