/* BIB Assurance - small page helpers (plain JavaScript + Bootstrap 5.3 bundle).
   Every helper looks for its own elements, so the file can load on every page. */
(function () {
  'use strict';

  const thb = (n) => '฿' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  /* 1) Bootstrap form validation (official "Validation" pattern) */
  document.querySelectorAll('form.needs-validation').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add('was-validated');
    }, false);
  });

  /* 2) Premium calculator on the product page */
  const calc = document.getElementById('premiumForm');
  if (calc) {
    const limits = JSON.parse(document.getElementById('tierLimits').textContent);
    const amount = document.getElementById('coverageInput');
    const range = document.getElementById('coverageRange');
    const ageInput = document.getElementById('ageInput');
    const out = {
      total: document.getElementById('premiumTotal'),
      monthly: document.getElementById('premiumMonthly'),
      coverage: document.getElementById('summaryCoverage'),
      plan: document.getElementById('summaryPlan'),
      age: document.getElementById('summaryAge'),
      risk: document.getElementById('summaryRisk'),
      term: document.getElementById('summaryTerm'),
      error: document.getElementById('premiumError'),
      submit: document.getElementById('quoteSubmit'),
    };
    let timer = null;

    const selectedTier = () => calc.querySelector('input[name="tier_id"]:checked');
    const selectedRisk = () => calc.querySelector('input[name="risk_level"]:checked');

    const applyLimits = () => {
      const tier = selectedTier();
      if (!tier) return;
      const lim = limits[tier.value];
      [amount, range].forEach((el) => { el.min = lim.min; el.max = lim.max; el.step = lim.step; });
      let v = Number(amount.value);
      if (!v || v < lim.min) v = lim.min;
      if (v > lim.max) v = lim.max;
      amount.value = v;
      range.value = v;
      document.getElementById('coverageMin').textContent = thb(lim.min).replace('.00', '');
      document.getElementById('coverageMax').textContent = thb(lim.max).replace('.00', '');
      out.plan.textContent = tier.dataset.label;
    };

    const refresh = () => {
      const tier = selectedTier();
      const risk = selectedRisk();
      if (!tier || !risk) return;
      const params = new URLSearchParams({ tier_id: tier.value, coverage: amount.value, risk_level: risk.value });
      if (ageInput) params.set('age', ageInput.value);
      fetch(calc.dataset.previewUrl + '?' + params.toString())
        .then((r) => r.json())
        .then((data) => {
          if (!data.ok) {
            out.error.textContent = data.message;
            out.error.classList.remove('d-none');
            out.total.textContent = '—';
            out.monthly.textContent = '—';
            if (out.submit) out.submit.disabled = true;
            return;
          }
          out.error.classList.add('d-none');
          out.total.textContent = data.premiumText;
          out.monthly.textContent = data.monthlyText;
          out.coverage.textContent = data.coverageText;
          out.age.textContent = data.ageLabel;
          out.risk.textContent = data.riskLabel;
          out.term.textContent = data.term;
          if (out.submit) out.submit.disabled = false;
        })
        .catch(() => {
          out.error.textContent = 'We could not calculate the premium right now. Please try again.';
          out.error.classList.remove('d-none');
        });
    };
    const later = () => { clearTimeout(timer); timer = setTimeout(refresh, 250); };

    calc.querySelectorAll('input[name="tier_id"]').forEach((el) => el.addEventListener('change', () => { applyLimits(); refresh(); }));
    calc.querySelectorAll('input[name="risk_level"]').forEach((el) => el.addEventListener('change', refresh));
    range.addEventListener('input', () => { amount.value = range.value; later(); });
    amount.addEventListener('input', () => { range.value = amount.value; later(); });
    if (ageInput) ageInput.addEventListener('input', later);
    document.querySelectorAll('[data-select-tier]').forEach((btn) => btn.addEventListener('click', () => {
      const radio = document.getElementById('tier' + btn.dataset.selectTier);
      radio.checked = true;
      radio.dispatchEvent(new Event('change'));
    }));
    applyLimits();
    refresh();
  }

  /* 3) Beneficiaries: running total of the benefit shares */
  const pctInputs = document.querySelectorAll('.js-pct');
  if (pctInputs.length) {
    const bar = document.getElementById('pctBar');
    const label = document.getElementById('pctTotal');
    const update = () => {
      let total = 0;
      pctInputs.forEach((el) => { total += Number(el.value) || 0; });
      total = Math.round(total * 100) / 100;
      label.textContent = total + '%';
      bar.style.width = Math.min(total, 100) + '%';
      bar.parentElement.setAttribute('aria-valuenow', total);
      bar.classList.remove('bg-success', 'bg-warning', 'bg-danger', 'bg-primary');
      bar.classList.add(total === 100 ? 'bg-success' : (total > 100 ? 'bg-danger' : 'bg-warning'));
    };
    pctInputs.forEach((el) => el.addEventListener('input', update));
    update();
  }

  /* 4) Checkout: show the card fields only for card payments */
  const methods = document.querySelectorAll('input[name="payment_method"]');
  if (methods.length) {
    const cardFields = document.getElementById('cardFields');
    const toggle = () => {
      const isCard = document.querySelector('input[name="payment_method"]:checked').value === 'Card';
      cardFields.classList.toggle('d-none', !isCard);
      cardFields.querySelectorAll('input').forEach((el) => { el.required = isCard; el.disabled = !isCard; });
      document.querySelectorAll('[data-method-note]').forEach((n) => {
        n.classList.toggle('d-none', n.dataset.methodNote !== document.querySelector('input[name="payment_method"]:checked').value);
      });
    };
    methods.forEach((el) => el.addEventListener('change', toggle));
    toggle();
    const cardNumber = document.getElementById('card_number');
    if (cardNumber) {
      cardNumber.addEventListener('input', () => {
        const digits = cardNumber.value.replace(/\D/g, '').slice(0, 16);
        cardNumber.value = digits.replace(/(.{4})/g, '$1 ').trim();
      });
    }
  }

  /* 5) Claim documents: preview the selected image */
  document.querySelectorAll('input[type="file"][data-preview]').forEach((input) => {
    input.addEventListener('change', () => {
      const img = document.getElementById(input.dataset.preview);
      if (input.files && input.files[0] && input.files[0].type.startsWith('image/')) {
        img.src = URL.createObjectURL(input.files[0]);
        img.classList.remove('d-none');
      } else {
        img.classList.add('d-none');
      }
    });
  });

  /* 6) Document viewer modal (claim pages) */
  const viewer = document.getElementById('documentModal');
  if (viewer) {
    viewer.addEventListener('show.bs.modal', (event) => {
      const trigger = event.relatedTarget;
      viewer.querySelector('.modal-title').textContent = trigger.dataset.docTitle || 'Document';
      const img = viewer.querySelector('img');
      img.src = trigger.dataset.docSrc;
      img.alt = trigger.dataset.docTitle || 'Document';
      viewer.querySelector('[data-doc-open]').href = trigger.dataset.docSrc;
    });
  }

  /* 7) Claim assessment: approved amount only for approvals, note templates */
  const decisions = document.querySelectorAll('input[name="decision"]');
  if (decisions.length) {
    const amountGroup = document.getElementById('approvedAmountGroup');
    const amountInput = document.getElementById('approved_amount');
    const note = document.getElementById('review_note');
    const toggle = () => {
      const picked = document.querySelector('input[name="decision"]:checked');
      const approve = picked && picked.value === 'Approved';
      if (amountGroup) {          // claims only; applications have no amount
        amountGroup.classList.toggle('d-none', !approve);
        amountInput.required = approve;
      }
      note.required = picked && picked.value === 'Rejected';
      document.querySelectorAll('[data-note-group]').forEach((g) => {
        g.classList.toggle('d-none', !picked || g.dataset.noteGroup !== picked.value);
      });
    };
    decisions.forEach((el) => el.addEventListener('change', toggle));
    document.querySelectorAll('[data-note]').forEach((btn) => btn.addEventListener('click', () => {
      note.value = btn.dataset.note;
    }));
    toggle();
  }

  /* 8) Application form: medical details only when "Yes" is selected */
  const medGroup = document.getElementById('healthDetailsGroup');
  if (medGroup) {
    const details = document.getElementById('health_details');
    const toggleMed = () => {
      const yes = document.getElementById('medYes').checked;
      medGroup.classList.toggle('d-none', !yes);
      details.required = yes;
    };
    document.querySelectorAll('input[name="has_medical_history"]').forEach((el) => el.addEventListener('change', toggleMed));
    toggleMed();
  }

  /* 9) Tooltips (Bootstrap requires opt-in initialisation) */
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));
})();
