const state = { activeTab: 'CONSENSUS_36', route: 'dashboard', meta: null, daily: { sort: 'newest', page: 1, pageSize: 50, showParity: false } };

const pct = (x) => ((x ?? 0) * 100).toFixed(2) + '%';
const fmt = (x) => Number(x ?? 0).toFixed(4);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Request failed');
  return payload;
}

async function init() {
  try {
    await refreshMeta();
    state.activeTab = 'CONSENSUS_36';
    wireNavigation();
    await loadEval();
  } catch (error) {
    showError(error);
  }
}

function wireNavigation() {
  document.querySelectorAll('.side-link').forEach((button) => button.addEventListener('click', () => navigate(button.dataset.route)));
  document.getElementById('sidebar-toggle').addEventListener('click', () => {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('is-collapsed');
    document.getElementById('sidebar-toggle').textContent = sidebar.classList.contains('is-collapsed') ? '→' : '←';
  });
}

function navigate(route) {
  state.route = route;
  document.querySelectorAll('.side-link').forEach((button) => button.classList.toggle('is-active', button.dataset.route === route));
  const labels = { dashboard: ['Command center', 'Dashboard'], predictions: ['Decision workspace', 'Predictions'], consensus: ['Decision workspace', '36 Consensus'], engines: ['Research workspace', 'Engine Lab'], data: ['Canonical dataset', 'Daily Data'], advanced: ['System workspace', 'Advanced'] };
  document.getElementById('page-kicker').textContent = labels[route][0];
  document.getElementById('page-title').textContent = labels[route][1];
  if (route === 'dashboard') { renderDashboard(); return; }
  if (route === 'data') { state.activeTab = 'DATA_IMPORT'; renderImport(); return; }
  if (route === 'consensus' || route === 'predictions') { state.activeTab = 'CONSENSUS_36'; renderConsensus(); return; }
  if (route === 'engines') { state.activeTab = state.activeTab === 'CONSENSUS_36' || state.activeTab === 'DATA_IMPORT' ? state.tabMeta.find((item) => item.name !== 'CONSENSUS_36' && item.name !== 'DATA_IMPORT')?.name : state.activeTab; renderEngineSelector(); renderEngine(); return; }
  renderAdvanced();
}

async function refreshMeta() {
  const meta = await api('/api/meta');
  const dateSelect = document.getElementById('date-select');
  const previous = dateSelect ? dateSelect.value : 'NEXT';

  dateSelect.innerHTML = '';
  meta.dates.slice().reverse().forEach((date) => {
    const option = document.createElement('option');
    option.value = date;
    option.textContent = date;
    dateSelect.appendChild(option);
  });

  const nextOption = document.createElement('option');
  nextOption.value = 'NEXT';
  nextOption.textContent = 'NEXT TARGET (latest history + 1 day)';
  dateSelect.insertBefore(nextOption, dateSelect.firstChild);
  dateSelect.value = previous && [...dateSelect.options].some((o) => o.value === previous) ? previous : 'NEXT';

  state.meta = meta;
  state.tabMeta = [{ name: 'DATA_IMPORT', kind: 'import' }, { name: 'CONSENSUS_36', kind: 'pool' }, ...meta.engines];
}

function renderTabs() {
  const tabs = document.getElementById('tabs');
  tabs.innerHTML = '';

  state.tabMeta.forEach((entry) => {
    const button = document.createElement('button');
    const kind = entry.kind || 'engine';
    button.type = 'button';
    button.className = `tab ${entry.name === state.activeTab ? 'is-active' : ''}`;
    button.dataset.kind = kind;
    button.textContent = entry.name === 'CONSENSUS_36' ? '36 CONSENSUS POOL' : entry.name === 'DATA_IMPORT' ? 'BULK DATA IMPORT' : entry.name;
    button.addEventListener('click', () => {
      state.activeTab = entry.name;
      renderTabs();
      renderMain();
    });
    tabs.appendChild(button);
  });
}

async function loadEval() {
  if (state.activeTab === 'DATA_IMPORT') {
    renderImport();
    return;
  }

  const status = document.getElementById('status');
  status.textContent = 'Loading';
  document.getElementById('app-content').innerHTML = '<div class="loading-panel"><span class="spinner"></span><div><strong>Running evaluation</strong><p>Calculating engine rankings and consensus evidence...</p></div></div>';
  const selectedDate = document.getElementById('date-select').value;
  try {
    const result = await api('/api/evaluate?date=' + encodeURIComponent(selectedDate));
    state.eval = result;
    status.textContent = `Target ${result.target_date}`;
    renderMain();
  } catch (error) {
    showError(error);
  }
}

function showError(error) {
  document.getElementById('status').textContent = 'Unavailable';
  document.getElementById('app-content').innerHTML = `<div class="error-panel"><strong>Could not load this view</strong><p>${error.message}</p><button type="button" onclick="loadEval()">Try again</button></div>`;
}

function outcomeLabel(rank) {
  if (!rank) return { className: '', text: 'Forward target · outcome not available' };
  if (rank <= 5) return { className: 'good', text: 'TOP-5 HIT' };
  if (rank <= 10) return { className: 'good', text: 'TOP-10' };
  if (rank <= 21) return { className: 'warn', text: 'TOP-21' };
  if (rank <= 36) return { className: 'warn', text: 'TOP-36' };
  return { className: 'bad', text: 'OUTSIDE TOP-36' };
}

function summaryStats() {
  const meta = state.meta || {};
  return `<div class="summary-stats">
    <div><span>History rows</span><strong>${meta.row_count || 0}</strong></div>
    <div><span>Engine registry</span><strong>${meta.engines?.length || 0}</strong></div>
    <div><span>Source cutoff</span><strong>${state.eval?.source_cutoff || '—'}</strong></div>
    <div><span>Target date</span><strong>${state.eval?.target_date || '—'}</strong></div>
  </div>`;
}

function renderMain() {
  const content = document.getElementById('app-content');
  if (state.route === 'dashboard') { renderDashboard(); return; }
  if (state.activeTab === 'DATA_IMPORT') {
    renderImport();
    return;
  }
  if (state.activeTab === 'CONSENSUS_36') {
    renderConsensus();
    return;
  }
  renderEngine();
}

function renderDashboard() {
  const content = document.getElementById('app-content');
  if (!state.eval) { content.innerHTML = '<div class="loading-panel"><span class="spinner"></span><div><strong>Building command center</strong><p>Loading the latest canonical evaluation...</p></div></div>'; return; }
  const consensus = state.eval.consensus;
  const cards = Object.entries(consensus.houses).map(([house, item]) => {
    const top = item.ranking.slice(0, 5);
    const lead = item.details?.[0];
    const metrics = item.metrics?.['30'] || item.metrics?.expanding;
    return `<article class="house-card"><div class="house-card-head"><div><div class="eyebrow">House</div><h3>${house}</h3></div><span class="status-badge ready">Ready</span></div><div class="primary-label">Primary support</div><strong class="primary-engine">${lead?.engines?.[0] || 'Consensus signal'}</strong><div class="candidate-label">Top-5 ranking</div><div class="top-five">${top.map((number, index) => `<span><small>#${index + 1}</small>${number}</span>`).join('')}</div><div class="house-card-footer"><div><span>H@5</span><strong>${metrics ? pct(metrics.h5) : '—'}</strong></div><div><span>Target</span><strong>${state.eval.target_date}</strong></div></div><button type="button" class="card-link" onclick="navigate('consensus')">View consensus <span>→</span></button></article>`;
  }).join('');
  content.innerHTML = `<section class="dashboard-hero"><div><div class="eyebrow">DHAPPA command center</div><h1>One clear view of the next target.</h1><p>Research-grade signals, organized around the four daily houses and the canonical dataset.</p></div><div class="hero-target"><span>Next target</span><strong>${formatDate(state.eval.target_date)}</strong><small>Source cutoff ${formatDate(state.eval.source_cutoff)}</small></div></section><div class="dashboard-stats"><div><span>Latest data</span><strong>${formatDate(state.meta.last_date)}</strong><small>Canonical dataset</small></div><div><span>Next target</span><strong>${formatDate(state.eval.target_date)}</strong><small>Prediction freeze</small></div><div><span>Model registry</span><strong>${state.meta.engines.length} engines</strong><small>Consensus ready</small></div><div><span>Integrity</span><strong class="good">PASS</strong><small>Local data source</small></div></div><div class="section-heading dashboard-heading"><div><div class="eyebrow">Decision surface</div><h2>House predictions</h2><p>Top candidates from the weighted 36 Consensus pool.</p></div><button type="button" class="secondary-button" onclick="navigate('data')">Open daily data →</button></div><div class="house-grid">${cards}</div><section class="intelligence-section"><div class="section-heading"><div><div class="eyebrow">Strict historical replay</div><h2>Engine performance intelligence</h2><p>Best-engine selections and daily hit counts come from freeze-first walk-forward evidence.</p></div><label class="tier-control">Tier<select id="dashboard-tier"><option value="5">Top-5</option><option value="10">Top-10</option><option value="21">Top-21</option><option value="36">Top-36</option></select></label></div><div id="best-engine-cards" class="best-engine-grid"><div class="table-loading">Loading best engine by house...</div></div><div class="intelligence-grid"><div class="leaderboard-card"><div class="subsection-heading"><h3>Engine leaderboard</h3><select id="leaderboard-house"><option value="DS">DS</option><option value="FB">FB</option><option value="GB">GB</option><option value="GL">GL</option></select></div><div id="leaderboard-table" class="table-wrap"><div class="table-loading">Loading leaderboard...</div></div></div><div class="daywise-card"><div class="subsection-heading"><h3>Day-wise validation</h3><span class="integrity-badge">FREEZE FIRST</span></div><div id="daywise-summary" class="dashboard-mini-summary"></div><div id="daywise-table" class="table-wrap"><div class="table-loading">Loading daily results...</div></div></div></div></section>`;
  loadDashboardIntelligence();
}

async function loadDashboardIntelligence() {
  try {
    const tier = document.getElementById('dashboard-tier').value;
    const best = await api('/api/walkforward/best-engine-by-house?tier=' + tier);
    document.getElementById('best-engine-cards').innerHTML = Object.values(best.data).map(item => `<article class="best-engine-card"><div class="eyebrow">${item.house}</div><h3>${item.best_engine}</h3><div class="best-rate"><strong>${pct(item.hit_rate)}</strong><span>H@${tier}</span></div><div class="best-engine-meta"><span>Recent 30 <b>${pct(item.recent_30_hit_rate)}</b></span><span>Samples <b>${item.samples}</b></span></div></article>`).join('');
    const leaderboardHouse = document.getElementById('leaderboard-house');
    const loadLeaderboard = async () => { const data = await api(`/api/walkforward/house-leaderboard?house=${leaderboardHouse.value}&tier=${tier}&window=expanding`); document.getElementById('leaderboard-table').innerHTML = `<table class="compact-table"><thead><tr><th>#</th><th>Engine</th><th>H@${tier}</th><th>H@10</th><th>MRR</th><th>N</th></tr></thead><tbody>${data.models.map(row => `<tr><td>${row.rank}</td><td>${row.model}</td><td>${pct(row[`h${tier}`])}</td><td>${pct(row.h10)}</td><td>${row.mrr.toFixed(3)}</td><td>${row.samples}</td></tr>`).join('')}</tbody></table>`; };
    leaderboardHouse.onchange = loadLeaderboard; await loadLeaderboard();
    const daily = await api(`/api/walkforward/daywise?model=CONSENSUS_36&tier=${tier}`); const recent = daily.data.slice(-12).reverse(); const summary = daily.summary; document.getElementById('daywise-summary').innerHTML = `<span>${summary.evaluated_days} days</span><span>${summary.sweeps} full sweeps</span><span>Avg ${summary.average_houses_hit.toFixed(2)} / 4</span>`; document.getElementById('daywise-table').innerHTML = `<table class="compact-table"><thead><tr><th>Date</th><th>DS</th><th>FB</th><th>GB</th><th>GL</th><th>Hit</th><th>Miss</th></tr></thead><tbody>${recent.map(row => `<tr><td>${formatDate(row.date)}</td>${['DS','FB','GB','GL'].map(h => `<td class="${row.houses[h].hit ? 'hit-cell' : 'miss-cell'}">${row.houses[h].hit ? 'HIT' : 'MISS'}</td>`).join('')}<td>${row.hits}/4</td><td>${row.misses}/4</td></tr>`).join('')}</tbody></table>`;
    document.getElementById('dashboard-tier').onchange = () => loadDashboardIntelligence();
  } catch (error) { document.getElementById('best-engine-cards').innerHTML = `<div class="error-panel"><strong>Performance intelligence unavailable</strong><p>${error.message}</p></div>`; }
}

function renderEngineSelector() {
  document.querySelectorAll('.engine-choice').forEach((button) => button.classList.toggle('is-active', button.dataset.engine === state.activeTab));
}

function renderAdvanced() {
  document.getElementById('app-content').innerHTML = `<section class="advanced-page"><div class="eyebrow">System workspace</div><h1>Advanced details</h1><p>Technical context stays available without crowding the daily decision surface.</p><div class="advanced-grid"><div><span>Dataset hash</span><strong>Available in audit logs</strong></div><div><span>Backups</span><strong>Created before each save</strong></div><div><span>Metrics</span><strong>Rebuilt after canonical updates</strong></div><div><span>Runtime</span><strong>Python local service</strong></div></div><details open><summary>Integrity and audit trail</summary><p>Every import and edit uses the canonical dataset path, creates a backup, reloads rows, and rebuilds historical engine and consensus metrics.</p></details></section>`;
}

function metricTable(metrics) {
  if (!metrics) return '<div class="meta">No historical profile available.</div>';

  const rows = ['15', '30', '60', 'expanding']
    .map((windowKey) => {
      const x = metrics[windowKey];
      return `
        <tr>
          <td>${windowKey}</td>
          <td>${x.n}</td>
          <td>${pct(x.h5)}</td>
          <td>${pct(x.h10)}</td>
          <td>${pct(x.h21)}</td>
          <td>${pct(x.h36)}</td>
          <td>${fmt(x.mrr)}</td>
          <td>${Number(x.mean_rank).toFixed(1)}</td>
        </tr>
      `;
    })
    .join('');

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Window</th>
            <th>N</th>
            <th>H@5</th>
            <th>H@10</th>
            <th>H@21</th>
            <th>H@36</th>
            <th>MRR</th>
            <th>Mean Rank</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function block(label, arr, actual, pool = false) {
  return `
    <div class="section">
      <div class="label">${label}</div>
      <div class="nums">
        ${arr.map((n, i) => `<span class="num ${i < 5 ? 'top5' : ''} ${n === actual ? 'actual' : ''} ${pool ? 'poolnum' : ''}">${n}</span>`).join('')}
      </div>
    </div>
  `;
}

function renderConsensus() {
  const content = document.getElementById('app-content');
  const houses = Object.entries(state.eval.consensus.houses);

  const cards = houses.map(([house, x]) => {
    const actual = x.actual;
    const outcome = outcomeLabel(x.actual_rank);
    const actualRow = actual ? `Actual <strong>${actual}</strong> · consensus rank <strong>${x.actual_rank}</strong> · <span class="${outcome.className}">${outcome.text}</span>` : outcome.text;

    const detailsRows = x.details.map((d) => `
      <tr>
        <td><span class="rankbadge">${d.rank}</span></td>
        <td>${d.number}</td>
        <td>${d.score.toFixed(3)}</td>
        <td>${d.support_count}/12</td>
        <td style="text-align:left;">${d.engines.join(', ') || '—'}</td>
      </tr>
    `).join('');

    return `
      <div class="card">
        <h3>${house}</h3>
        <div class="actual-row">${actualRow}</div>
        ${block('Top 5', x.ranking.slice(0,5), actual, true)}
        ${block('Ranks 6–10', x.ranking.slice(5,10), actual, true)}
        ${block('Ranks 11–21', x.ranking.slice(10,21), actual, true)}
        ${block('Ranks 22–36', x.ranking.slice(21,36), actual, true)}
        <div class="section">
          <div class="label">Historical 36 Consensus performance</div>
          ${metricTable(x.metrics)}
        </div>
        <div class="section">
          <div class="label">Top-36 candidate evidence</div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Number</th>
                  <th>Score</th>
                  <th>Support</th>
                  <th style="text-align:left;">Engines</th>
                </tr>
              </thead>
              <tbody>${detailsRows}</tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }).join('');

  content.innerHTML = `
    <div class="hero" data-kind="pool">
      <div>
        <h2>36 CONSENSUS POOL</h2>
        <span class="pill pool">Weighted Borda • Current 12-engine registry</span>
        <p>Each engine contributes its frozen Top-36. Imported data immediately feeds this panel after validation and metrics rebuild.</p>
      </div>
    </div>
    ${summaryStats()}
    <div class="grid">${cards}</div>
    <section id="consensus-walkforward" class="walkforward-panel"><div class="loading-panel"><span class="spinner"></span><div><strong>Building walk-forward validation</strong><p>Replaying each target with source history frozen before the draw.</p></div></div></section>
  `;
  loadWalkforwardGrid('CONSENSUS_36', 'consensus-walkforward');
}

function renderEngine() {
  const content = document.getElementById('app-content');
  const selectedEngine = state.eval.engines.find((engine) => engine.name === state.activeTab);
  if (!selectedEngine) return;

  const cards = Object.entries(selectedEngine.houses).map(([house, x]) => {
    const actual = x.actual;
    const outcome = outcomeLabel(x.actual_rank);
    const actualRow = actual ? `Actual <strong>${actual}</strong> · rank <strong>${x.actual_rank}</strong> · <span class="${outcome.className}">${outcome.text}</span>` : outcome.text;

    return `
      <div class="card">
        <h3>${house}</h3>
        <div class="actual-row">${actualRow}</div>
        ${block('Top 5', x.ranking.slice(0,5), actual)}
        ${block('Ranks 6–10', x.ranking.slice(5,10), actual)}
        ${block('Ranks 11–21', x.ranking.slice(10,21), actual)}
        ${block('Ranks 22–36', x.ranking.slice(21,36), actual)}
        <div class="section">
          <div class="label">Historical performance</div>
          ${metricTable(x.metrics)}
        </div>
        <div class="meta">Engine meta: ${JSON.stringify(x.meta)}</div>
      </div>
    `;
  }).join('');

  const engineChoices = state.tabMeta.filter((entry) => entry.kind !== 'pool' && entry.kind !== 'import').map((entry) => `<button type="button" class="engine-choice ${entry.name === state.activeTab ? 'is-active' : ''}" data-engine="${entry.name}" onclick="state.activeTab='${entry.name}'; renderEngine()"><span>${entry.name}</span><small>${entry.kind || 'Engine'}</small></button>`).join('');
  content.innerHTML = `<div class="engine-layout"><aside class="engine-list"><div class="eyebrow">12 active models</div><h2>Engine registry</h2><input placeholder="Search engines..." aria-label="Search engines" oninput="filterEngines(this.value)"><div id="engine-choices">${engineChoices}</div></aside><div class="engine-detail"><div class="hero"><div><div class="eyebrow">Canonical model</div><h2>${selectedEngine.name}</h2><span class="pill">${selectedEngine.family}</span><p>${selectedEngine.description}</p></div></div>${summaryStats()}<div class="grid">${cards}</div><section id="engine-walkforward" class="walkforward-panel"><div class="loading-panel"><span class="spinner"></span><div><strong>Building walk-forward validation</strong><p>Replaying each target with source history frozen before the draw.</p></div></div></section></div></div>`;
  loadWalkforwardGrid(state.activeTab, 'engine-walkforward');
}

function filterEngines(value) { const query = value.trim().toLowerCase(); document.querySelectorAll('.engine-choice').forEach((button) => button.hidden = query && !button.textContent.toLowerCase().includes(query)); }

async function loadWalkforwardGrid(model, id) {
  const host = document.getElementById(id); if (!host) return;
  const houses = ['DS','FB','GB','GL'];
  try {
    const results = await Promise.all(houses.map((house) => api((model === 'CONSENSUS_36' ? '/api/consensus/36/walkforward' : `/api/engines/${model.toLowerCase()}/walkforward`) + `?house=${house}&window=expanding`)));
    const daywise = await api(`/api/walkforward/daywise?model=${encodeURIComponent(model)}&tier=5`);
    const rows = results.map((result, index) => { const m = result.metrics; return `<tr><td><strong>${houses[index]}</strong></td><td>${pct(m.h5)}</td><td>${pct(m.h10)}</td><td>${pct(m.h21)}</td><td>${pct(m.h36)}</td><td>${m.mrr.toFixed(3)}</td><td>${m.samples}</td><td><span class="evidence-badge ${m.evidence.toLowerCase().replaceAll('_','-')}">${m.evidence.replaceAll('_',' ')}</span></td></tr>`; }).join('');
    const replay = results[0].records.slice(-15).reverse().map((row) => `<tr><td>${formatDate(row.target_date)}</td><td>${formatDate(row.source_cutoff)}</td><td>${row.actual || '—'}</td><td>${row.actual_rank || '—'}</td><td>${row.top5 ? '✓' : '—'}</td><td>${row.top10 ? '✓' : '—'}</td><td>${row.top21 ? '✓' : '—'}</td><td>${row.top36 ? '✓' : '—'}</td><td><code>${row.freeze_hash}</code></td></tr>`).join('');
    const daywiseRows = daywise.data.slice().reverse().map((row) => `<tr><td>${formatDate(row.date)}</td><td>${row.day}</td>${['DS','FB','GB','GL'].map((house) => `<td class="${row.houses[house].hit ? 'hit-cell' : 'miss-cell'}">${row.houses[house].hit ? 'HIT' : 'MISS'}</td>`).join('')}<td>${row.hits}/4</td><td>${row.misses}/4</td><td>${row.sweep}</td></tr>`).join('');
    host.innerHTML = `<div class="walkforward-heading"><div><div class="eyebrow">Strict temporal replay</div><h2>${model === 'CONSENSUS_36' ? 'Consensus' : model} walk-forward performance</h2><p>Source history is frozen before each target. Actual outcomes are revealed only after prediction.</p></div><span class="integrity-badge">✓ FREEZE FIRST</span></div><div class="validation-strip"><div><span>Primary view</span><strong>Expanding history</strong></div><div><span>Recent view</span><strong>Last 30 targets</strong></div><div><span>Integrity</span><strong class="good">PASS</strong></div></div><div class="table-wrap"><table class="validation-table"><thead><tr><th>House</th><th>H@5</th><th>H@10</th><th>H@21</th><th>H@36</th><th>MRR</th><th>Samples</th><th>Evidence</th></tr></thead><tbody>${rows}</tbody></table></div><details class="advanced-details"><summary>Walk-forward history · last 15 ${results[0].records.length ? `of ${results[0].records.length}` : ''} records</summary><div class="table-wrap"><table class="validation-table"><thead><tr><th>Target</th><th>Cutoff</th><th>Actual</th><th>Rank</th><th>H@5</th><th>H@10</th><th>H@21</th><th>H@36</th><th>Freeze hash</th></tr></thead><tbody>${replay}</tbody></table></div></details><section class="daywise-validation"><div class="subsection-heading"><div><div class="eyebrow">Date-level replay</div><h3>Day-wise validation</h3><p>How this model performed across all four houses on each historical target.</p></div><label class="tier-control">Tier<select onchange="loadEngineDaywise(this.value, '${model}', '${id}')"><option value="5">Top-5</option><option value="10">Top-10</option><option value="21">Top-21</option><option value="36">Top-36</option></select></label></div><div class="daywise-summary"><span>${daywise.summary.evaluated_days} evaluated days</span><span>${daywise.summary.sweeps} full sweeps</span><span>Average ${daywise.summary.average_houses_hit.toFixed(2)} / 4 houses hit</span></div><div id="${id}-daywise-table" class="table-wrap"><table class="validation-table"><thead><tr><th>Date</th><th>Day</th><th>DS</th><th>FB</th><th>GB</th><th>GL</th><th>Hit</th><th>Miss</th><th>Classification</th></tr></thead><tbody>${daywiseRows}</tbody></table></div></section></section>`;
  } catch (error) { host.innerHTML = `<div class="error-panel"><strong>Walk-forward validation unavailable</strong><p>${error.message}</p><button type="button" onclick="loadWalkforwardGrid('${model}','${id}')">Retry</button></div>`; }
}

async function loadEngineDaywise(tier, model, id) {
  const table = document.getElementById(`${id}-daywise-table`); if (!table) return;
  try {
    const daywise = await api(`/api/walkforward/daywise?model=${encodeURIComponent(model)}&tier=${tier}`);
    const rows = daywise.data.slice().reverse().map((row) => `<tr><td>${formatDate(row.date)}</td><td>${row.day}</td>${['DS','FB','GB','GL'].map((house) => `<td class="${row.houses[house].hit ? 'hit-cell' : 'miss-cell'}">${row.houses[house].hit ? 'HIT' : 'MISS'}</td>`).join('')}<td>${row.hits}/4</td><td>${row.misses}/4</td><td>${row.sweep}</td></tr>`).join('');
    table.innerHTML = `<table class="validation-table"><thead><tr><th>Date</th><th>Day</th><th>DS</th><th>FB</th><th>GB</th><th>GL</th><th>Hit</th><th>Miss</th><th>Classification</th></tr></thead><tbody>${rows}</tbody></table>`;
    const summary = table.previousElementSibling; if (summary) summary.innerHTML = `<span>${daywise.summary.evaluated_days} evaluated days</span><span>${daywise.summary.sweeps} full sweeps</span><span>Average ${daywise.summary.average_houses_hit.toFixed(2)} / 4 houses hit</span>`;
  } catch (error) { table.innerHTML = `<div class="table-empty">${error.message}</div>`; }
}

function renderImport() {
  const meta = state.meta || { row_count: 0, first_date: '', last_date: '' };
  const content = document.getElementById('app-content');
  content.innerHTML = `
    <div class="hero" data-kind="import">
      <div>
        <h2>Bulk Data Import</h2>
        <span class="pill import">CSV • paste • single row</span>
        <p>Import historical draw data safely. Each commit creates a timestamped backup, validates dates and 00–99 values, merges duplicate dates deterministically, and rebuilds the engine and consensus metrics.</p>
      </div>
    </div>
    <div id="latest-draw" class="latest-draw"></div>
    <div class="dataset-strip">
      <div><span>Current dataset</span><strong>${meta.row_count || 0} dates</strong></div>
      <div><span>Range</span><strong>${formatDate(meta.first_date)} → ${formatDate(meta.last_date)}</strong></div>
      <div><span>DS recorded</span><strong id="count-ds">—</strong></div>
      <div><span>FB recorded</span><strong id="count-fb">—</strong></div>
      <div><span>GB recorded</span><strong id="count-gb">—</strong></div>
      <div><span>GL recorded</span><strong id="count-gl">—</strong></div>
    </div>
    <div class="import-grid">
      <div class="import-box">
        <div class="step-kicker">Step 01</div>
        <h3>Upload a CSV</h3>
        <label class="filedrop">Choose CSV
          <input id="csv-file" type="file" accept=".csv,text/csv" style="display:block;margin:10px auto 0;" onchange="readCsv(this)">
        </label>
        <div class="muted-box">Supported headers: Date, Deshawar/DS, Faridabad/FB, Ghaziabad/GB, Gali/GL. Values must be 00–99 or blank.</div>
        <div class="action-row">
          <select id="strategy">
            <option value="merge">MERGE with current data</option>
            <option value="replace">REPLACE current data</option>
          </select>
          <button type="button" onclick="previewCsv()">Preview &amp; Validate</button>
          <button type="button" onclick="commitCsv()">Import CSV</button>
        </div>
        <div id="csv-preview" class="preview">No file loaded.</div>
      </div>

      <div class="import-box">
        <div class="step-kicker">Step 02</div>
        <h3>Paste line items</h3>
        <textarea id="lines" placeholder="One row per line, no header:\n2026-09-20,35,21,07,86\n2026-09-21,42,18,55,09\n\nOrder: Date, Deshawar, Faridabad, Ghaziabad, Gali"></textarea>
        <div class="action-row">
          <button type="button" onclick="previewLines()">Preview Lines</button>
          <button type="button" onclick="commitLines()">Import Lines</button>
        </div>
        <div id="line-preview" class="preview">Ready for line-wise bulk paste.</div>
      </div>

      <div class="import-box" style="grid-column:1 / -1;">
        <div class="step-kicker">Step 03</div>
        <h3>Add one row</h3>
        <div class="row-form">
          <input id="r-date" placeholder="YYYY-MM-DD">
          <input id="r-ds" placeholder="DS">
          <input id="r-fb" placeholder="FB">
          <input id="r-gb" placeholder="GB">
          <input id="r-gl" placeholder="GL">
        </div>
        <div class="action-row">
          <button type="button" onclick="commitSingle()">Save single row</button>
        </div>
        <div id="single-preview" class="preview">No single-row entry yet.</div>
      </div>
    </div>
    <section class="daily-section">
      <div class="section-heading">
        <div><div class="eyebrow">Canonical dataset</div><h2>Daily Draw Data</h2><p>One row per date. Latest recorded results stay at the top.</p></div>
        <button type="button" class="primary-button" onclick="openDailyEditor()">+ Add daily result</button>
      </div>
      <div class="daily-toolbar">
        <input id="daily-search" placeholder="Search date or number..." aria-label="Search date or number">
        <label>From <input id="daily-from" type="date"></label>
        <label>To <input id="daily-to" type="date"></label>
        <select id="daily-house" aria-label="Filter house"><option value="ALL">All houses</option><option value="DS">DS · Deshawar</option><option value="FB">FB · Faridabad</option><option value="GB">GB · Ghaziabad</option><option value="GL">GL · Gali</option></select>
        <select id="daily-sort" aria-label="Sort order"><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select>
        <select id="daily-page-size" aria-label="Rows per page"><option value="25">25 rows</option><option value="50" selected>50 rows</option><option value="100">100 rows</option></select>
        <button type="button" onclick="setDailyPreset(7)">Last 7 days</button><button type="button" onclick="setDailyPreset(15)">15 days</button><button type="button" onclick="setDailyPreset(30)">30 days</button><button type="button" onclick="setDailyPreset(90)">90 days</button><button type="button" onclick="setDailyMonth(false)">This month</button><button type="button" onclick="setDailyMonth(true)">Previous month</button><button type="button" onclick="clearDailyFilters()">All data</button>
        <label class="toggle-label"><input id="daily-parity" type="checkbox"> Show parity</label>
        <button type="button" onclick="exportDaily()">Export table</button>
      </div>
      <div id="daily-table" class="daily-table-wrap"></div>
      <div id="daily-pagination" class="pagination"></div>
    </section>
    <dialog id="daily-dialog" class="daily-dialog"><form method="dialog" onsubmit="saveDailyEditor(event)"><div class="dialog-heading"><div><div class="eyebrow">Canonical dataset</div><h2 id="daily-dialog-title">Add daily result</h2></div><button type="button" class="icon-button" onclick="closeDailyEditor()" aria-label="Close">×</button></div><label>Date<input id="edit-date" type="date" required></label><div class="row-form"><label>DS<input id="edit-ds" inputmode="numeric" maxlength="2" placeholder="00"></label><label>FB<input id="edit-fb" inputmode="numeric" maxlength="2" placeholder="00"></label><label>GB<input id="edit-gb" inputmode="numeric" maxlength="2" placeholder="00"></label><label>GL<input id="edit-gl" inputmode="numeric" maxlength="2" placeholder="00"></label></div><p class="dialog-note">Use blank for not recorded. Valid draws are 00–99.</p><div class="action-row"><button type="button" onclick="closeDailyEditor()">Cancel</button><button type="submit" class="primary-button">Save and rebuild</button></div></form></dialog>
  `;

  document.getElementById('status').textContent = `Dataset: ${meta.row_count || 0} rows · ${meta.first_date || ''} to ${meta.last_date || ''}`;
  document.getElementById('daily-sort').value = state.daily.sort;
  document.getElementById('daily-page-size').value = String(state.daily.pageSize);
  document.getElementById('daily-parity').checked = state.daily.showParity;
  ['daily-search','daily-from','daily-to','daily-house','daily-sort','daily-page-size'].forEach((id) => document.getElementById(id).addEventListener('change', () => { state.daily.page = 1; loadDaily(); }));
  document.getElementById('daily-parity').addEventListener('change', (event) => { state.daily.showParity = event.target.checked; loadDaily(); });
  document.getElementById('daily-search').addEventListener('input', debounce(() => { state.daily.page = 1; loadDaily(); }, 180));
  loadDaily();
}

function debounce(fn, wait) { let timer; return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), wait); }; }
function formatDate(value) { if (!value) return '—'; const date = new Date(`${value}T00:00:00`); return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }); }
function drawValue(value) { return value == null || value === '' ? '—' : String(value).padStart(2, '0'); }
function parity(value) { return value == null || value === '' ? '' : Number(value) % 2 ? 'Odd' : 'Even'; }

async function loadDaily() {
  const table = document.getElementById('daily-table');
  if (!table) return;
  const params = new URLSearchParams({ page: state.daily.page, page_size: state.daily.pageSize, sort: state.daily.sort, search: document.getElementById('daily-search').value, from: document.getElementById('daily-from').value, to: document.getElementById('daily-to').value, house: document.getElementById('daily-house').value });
  table.innerHTML = '<div class="table-loading">Loading daily records...</div>';
  try {
    const payload = await api('/api/data/daily?' + params.toString());
    state.daily.payload = payload;
    renderDailyTable(payload);
    if (state.meta?.last_date) {
      const latest = await api('/api/data/daily/' + state.meta.last_date);
      renderLatestDraw(latest.data);
    }
    updateDailyStats(payload.meta);
  } catch (error) { table.innerHTML = `<div class="table-empty">${error.message}</div>`; }
}

function updateDailyStats(meta) { ['ds','fb','gb','gl'].forEach((key) => { const el = document.getElementById(`count-${key}`); if (el) el.textContent = `${meta.recorded[key === 'ds' ? 'Deshawar' : key === 'fb' ? 'Faridabad' : key === 'gb' ? 'Ghaziabad' : 'Gali'] || 0} rows`; }); }
function renderLatestDraw(row) { document.getElementById('latest-draw').innerHTML = row ? `<div><div class="eyebrow">Latest recorded draw</div><h2>${formatDate(row.date)} <span>${row.day}</span></h2></div><div class="latest-values">${[['DS','DS'],['FB','FB'],['GB','GB'],['GL','GL']].map(([label,key]) => `<div><span>${label}</span><strong>${drawValue(row[key])}</strong></div>`).join('')}</div>` : '<div class="table-empty">No recorded draws found.</div>'; }
function renderDailyTable(payload) {
  renderLatestDraw(payload.data[0] || null);
  const rows = payload.data || [];
  if (!rows.length) { document.getElementById('daily-table').innerHTML = '<div class="table-empty">No daily records match these filters.</div>'; document.getElementById('daily-pagination').innerHTML = ''; return; }
  document.getElementById('daily-table').innerHTML = `<table class="daily-table"><thead><tr><th>Date</th><th>Day</th><th title="Deshawar">DS</th><th title="Faridabad">FB</th><th title="Ghaziabad">GB</th><th title="Gali">GL</th><th>Action</th></tr></thead><tbody>${rows.map(row => `<tr data-date="${row.date}" onclick="showDailyDetails('${row.date}')"><td class="freeze-date">${formatDate(row.date)}</td><td class="freeze-day">${row.day}</td><td>${drawValue(row.DS)}</td><td>${drawValue(row.FB)}</td><td>${drawValue(row.GB)}</td><td>${drawValue(row.GL)}</td><td><button type="button" class="table-action" onclick="event.stopPropagation();openDailyEditor('${row.date}')">Edit</button></td></tr>`).join('')}</tbody></table>`;
  const meta = payload.meta; document.getElementById('daily-pagination').innerHTML = `<span>${meta.filtered_rows} matching dates · page ${meta.page} of ${meta.pages}</span><div><button type="button" ${meta.page <= 1 ? 'disabled' : ''} onclick="changeDailyPage(-1)">Previous</button><button type="button" ${meta.page >= meta.pages ? 'disabled' : ''} onclick="changeDailyPage(1)">Next</button></div>`;
}
function changeDailyPage(delta) { state.daily.page += delta; loadDaily(); }
function setDailyPreset(days) { const latest = state.meta?.last_date || new Date().toISOString().slice(0,10); const end = new Date(`${latest}T00:00:00`); const start = new Date(end); start.setDate(start.getDate() - days + 1); document.getElementById('daily-to').value = latest; document.getElementById('daily-from').value = start.toISOString().slice(0,10); state.daily.page = 1; loadDaily(); }
function setDailyMonth(previous) { const latest = state.meta?.last_date || new Date().toISOString().slice(0,10); const anchor = new Date(`${latest}T00:00:00`); const year = anchor.getFullYear(); const month = anchor.getMonth() - (previous ? 1 : 0); const start = new Date(year, month, 1); const end = previous ? new Date(year, month + 1, 0) : anchor; document.getElementById('daily-from').value = start.toISOString().slice(0,10); document.getElementById('daily-to').value = end.toISOString().slice(0,10); state.daily.page = 1; loadDaily(); }
function clearDailyFilters() { ['daily-search','daily-from','daily-to'].forEach(id => document.getElementById(id).value = ''); document.getElementById('daily-house').value = 'ALL'; state.daily.page = 1; loadDaily(); }
function exportDaily() { const ids = ['daily-from','daily-to','daily-search','daily-house','daily-sort']; const params = new URLSearchParams({ from: document.getElementById(ids[0]).value, to: document.getElementById(ids[1]).value, search: document.getElementById(ids[2]).value, house: document.getElementById(ids[3]).value, sort: document.getElementById(ids[4]).value }); window.location.href = '/api/data/export?' + params.toString(); }
async function showDailyDetails(date) { try { const result = await api('/api/data/daily/' + date); const row = result.data; const detail = (key) => `${drawValue(row[key])}${state.daily.showParity ? ` — ${parity(row[key])}` : ''}`; alert(`${formatDate(row.date)} · ${row.day}\n\nDS  ${detail('DS')}\nFB  ${detail('FB')}\nGB  ${detail('GB')}\nGL  ${detail('GL')}`); } catch (error) { alert(error.message); } }
function openDailyEditor(date = '') { const dialog = document.getElementById('daily-dialog'); document.getElementById('daily-dialog-title').textContent = date ? 'Edit daily result' : 'Add daily result'; document.getElementById('edit-date').value = date; ['ds','fb','gb','gl'].forEach(key => document.getElementById(`edit-${key}`).value = ''); if (date) { const row = state.daily.payload?.data.find(item => item.date === date); if (row) ['ds','fb','gb','gl'].forEach(key => document.getElementById(`edit-${key}`).value = row[key] || ''); document.getElementById('edit-date').readOnly = true; } else document.getElementById('edit-date').readOnly = false; dialog.showModal(); }
function closeDailyEditor() { document.getElementById('daily-dialog')?.close(); }
async function saveDailyEditor(event) { event.preventDefault(); const date = document.getElementById('edit-date').value; const body = { date, DS: document.getElementById('edit-ds').value, FB: document.getElementById('edit-fb').value, GB: document.getElementById('edit-gb').value, GL: document.getElementById('edit-gl').value }; const existing = state.daily.payload?.data.find(row => row.date === date); if (existing && !confirm('Update this recorded date? A backup will be created.')) return; try { await api(existing ? `/api/data/daily/${date}` : '/api/data/daily', { method: existing ? 'PATCH' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) }); closeDailyEditor(); await refreshMeta(); renderImport(); } catch (error) { alert(error.message); } }

function renderPreviewTable(rows) {
  if (!rows || !rows.length) return '';
  return `
    <div class="preview-table">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>DS</th>
            <th>FB</th>
            <th>GB</th>
            <th>GL</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${row.date}</td>
              <td>${drawValue(row.Deshawar)}</td>
              <td>${drawValue(row.Faridabad)}</td>
              <td>${drawValue(row.Ghaziabad)}</td>
              <td>${drawValue(row.Gali)}</td>
              <td><span class="import-status ${String(row.status || '').toLowerCase()}">${row.status || 'VALID'}</span>${row.changes && Object.keys(row.changes).length ? `<div class="change-note">${Object.entries(row.changes).map(([house, change]) => `${house}: ${drawValue(change.existing)} → ${drawValue(change.incoming)}`).join('<br>')}</div>` : ''}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function showPreview(id, payload) {
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const summary = `<div class="preview-summary"><strong>Import preview</strong><span>${payload.valid_rows} valid</span><span>${payload.new_dates} new</span><span>${payload.dates_with_changes} value changes</span><span>${payload.error_count} errors</span></div>`;
  const errors = payload.errors && payload.errors.length ? `\n\nErrors:\n${payload.errors.join('\n')}` : '';
  document.getElementById(id).innerHTML = `${summary}${errors}${renderPreviewTable(rows)}`;
}

async function readCsv(fileInput) {
  const file = fileInput.files[0];
  if (!file) return;
  window.importText = await file.text();
  document.getElementById('csv-preview').textContent = `Loaded ${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
}

async function previewCsv() {
  try {
    const payload = await api('/api/import/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: window.importText || '', has_header: true })
    });
    showPreview('csv-preview', payload);
  } catch (error) {
    document.getElementById('csv-preview').textContent = error.message;
  }
}

async function commitCsv() {
  if (!window.importText) {
    alert('Choose a CSV first');
    return;
  }
  if (!confirm('Commit this CSV import? A backup will be created.')) return;

  const el = document.getElementById('csv-preview');
  el.textContent = 'Importing and rebuilding metrics…';

  try {
    const result = await api('/api/import/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: window.importText,
        has_header: true,
        strategy: document.getElementById('strategy').value
      })
    });
    el.textContent = `SUCCESS\nRows: ${result.rows_after_import}\nRange: ${result.first_date} → ${result.last_date}\nMetrics rebuilt: ${result.metrics_rebuilt}`;
    await refreshMeta();
    renderImport();
  } catch (error) {
    el.textContent = 'FAILED: ' + error.message;
  }
}

async function previewLines() {
  const text = document.getElementById('lines').value;
  try {
    const payload = await api('/api/import/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, has_header: false })
    });
    showPreview('line-preview', payload);
  } catch (error) {
    document.getElementById('line-preview').textContent = error.message;
  }
}

async function commitLines() {
  const text = document.getElementById('lines').value;
  if (!text.trim()) {
    alert('Paste one or more rows first');
    return;
  }

  const el = document.getElementById('line-preview');
  el.textContent = 'Importing and rebuilding metrics…';

  try {
    const result = await api('/api/import/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, has_header: false, strategy: 'merge' })
    });
    el.textContent = `SUCCESS · ${result.rows_after_import} total rows · through ${result.last_date}`;
    await refreshMeta();
    renderImport();
  } catch (error) {
    el.textContent = 'FAILED: ' + error.message;
  }
}

async function commitSingle() {
  const values = ['r-date', 'r-ds', 'r-fb', 'r-gb', 'r-gl']
    .map((id) => document.getElementById(id).value.trim());

  const text = values.join(',');
  const el = document.getElementById('single-preview');
  el.textContent = 'Saving and rebuilding metrics…';

  try {
    const result = await api('/api/import/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, has_header: false, strategy: 'merge' })
    });
    el.textContent = `SUCCESS · ${values[0]} saved · ${result.rows_after_import} total rows`;
    await refreshMeta();
    renderImport();
  } catch (error) {
    el.textContent = 'FAILED: ' + error.message;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('date-select').addEventListener('change', async () => {
    if (state.activeTab !== 'DATA_IMPORT') {
      await loadEval();
    }
  });

  document.getElementById('refresh-btn').addEventListener('click', async () => {
    if (state.activeTab !== 'DATA_IMPORT') {
      await loadEval();
    } else {
      renderImport();
    }
  });

  init();
});
