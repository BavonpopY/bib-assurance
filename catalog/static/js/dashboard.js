/* BIB Assurance - administrator dashboard charts (Chart.js 4.4.7 from jsDelivr).
   Series colours were checked with a colour-vision palette validator:
   blue #256abf + gold #c98500 pass the CVD separation checks; every chart also
   has a "View data" table, so values never depend on colour alone. */
(function () {
  'use strict';
  if (!window.Chart) return;
  const data = JSON.parse(document.getElementById('chartData').textContent);
  const BLUE = '#256abf';
  const GOLD = '#c98500';
  const INK = '#52514e';
  const GRID = '#e1e0d9';
  const thb = (v) => '฿' + Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 });
  const compact = (v) => '฿' + Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(v);

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
  Chart.defaults.color = INK;
  Chart.defaults.plugins.tooltip.backgroundColor = '#0A1D37';
  Chart.defaults.plugins.tooltip.padding = 10;

  const hbar = (id, labels, values, fmt, tick = (v) => v) => new Chart(document.getElementById(id), {
    type: 'bar',
    data: { labels: labels, datasets: [{ data: values, backgroundColor: BLUE, borderRadius: 4, borderSkipped: 'start', barThickness: 16 }] },
    options: {
      indexAxis: 'y', maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => fmt(c.parsed.x) } } },
      scales: {
        x: { beginAtZero: true, grid: { color: GRID }, border: { display: false },
             ticks: { precision: 0, maxRotation: 0, callback: tick } },
        y: { grid: { display: false }, border: { color: '#c3c2b7' } },
      },
    },
  });

  // 1) net premium vs benefits paid - one axis (both in THB), two 2px lines
  new Chart(document.getElementById('chartMonthly'), {
    type: 'line',
    data: {
      labels: data.monthly.labels,
      datasets: [
        { label: 'Net premium', data: data.monthly.premium, borderColor: BLUE, backgroundColor: BLUE, borderWidth: 2,
          pointRadius: 4, pointHoverRadius: 6, pointBorderColor: '#fff', pointBorderWidth: 2, cubicInterpolationMode: 'monotone' },
        { label: 'Benefits paid', data: data.monthly.payout, borderColor: GOLD, backgroundColor: GOLD, borderWidth: 2,
          pointRadius: 4, pointHoverRadius: 6, pointBorderColor: '#fff', pointBorderWidth: 2, pointStyle: 'rectRot', cubicInterpolationMode: 'monotone' },
      ],
    },
    options: {
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', align: 'start', labels: { usePointStyle: true, boxWidth: 8 } },
        tooltip: { callbacks: { label: (c) => c.dataset.label + ': ' + thb(c.parsed.y) } },
      },
      scales: {
        y: { beginAtZero: true, grid: { color: GRID }, border: { display: false }, ticks: { callback: (v) => compact(v) } },
        x: { grid: { display: false }, border: { color: '#c3c2b7' } },
      },
    },
  });

  hbar('chartStatus', data.status.labels, data.status.values, (v) => v + ' claims');
  hbar('chartBest', data.best.labels, data.best.values, (v) => v + ' policies');
  hbar('chartLoss', data.loss.labels, data.loss.values, (v) => Number(v).toFixed(1) + '%', (v) => v + '%');

  // 5) policies by age band - vertical bars
  new Chart(document.getElementById('chartAges'), {
    type: 'bar',
    data: { labels: data.ages.labels, datasets: [{ data: data.ages.values, backgroundColor: BLUE, borderRadius: 4, borderSkipped: 'start', barThickness: 28 }] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => c.parsed.y + ' policies' } } },
      scales: {
        y: { beginAtZero: true, grid: { color: GRID }, border: { display: false }, ticks: { precision: 0 } },
        x: { grid: { display: false }, border: { color: '#c3c2b7' } },
      },
    },
  });
})();
