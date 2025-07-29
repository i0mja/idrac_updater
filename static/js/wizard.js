// SPDX-License-Identifier: Apache-2.0
let step = 1;
const wizard = document.getElementById('update-wizard');
const nextBtn = wizard?.querySelector('.next');
const prevBtn = wizard?.querySelector('.prev');
const finishBtn = wizard?.querySelector('.finish');

function showStep() {
  wizard.querySelectorAll('.step').forEach((el, i) => {
    el.style.display = i + 1 === step ? 'block' : 'none';
  });
  prevBtn.disabled = step === 1;
  nextBtn.style.display = step === 3 ? 'none' : 'inline-block';
  finishBtn.style.display = step === 3 ? 'inline-block' : 'none';
}

export function openWizard() {
  step = 1;
  wizard.classList.remove('hidden');
  fetch('/api/v1/firmware').then(r => r.json()).then(pkgs => {
    const sel = wizard.querySelector('select[name=firmware]');
    sel.innerHTML = '';
    pkgs.forEach(p => sel.append(new Option(p.filename, p.id)));
  });
  showStep();
}

nextBtn?.addEventListener('click', () => { step++; showStep(); });
prevBtn?.addEventListener('click', () => { step--; showStep(); });
finishBtn?.addEventListener('click', () => {
  const data = {
    name: wizard.querySelector('input[name=name]').value,
    firmware_id: wizard.querySelector('select[name=firmware]').value,
    host_ids: Array.from(wizard.querySelector('select[name=hosts]').selectedOptions).map(o => Number(o.value)),
    run_at: wizard.querySelector('input[name=run_at]').value || null
  };
  fetch('/api/v1/updates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  }).then(() => wizard.classList.add('hidden'));
});
