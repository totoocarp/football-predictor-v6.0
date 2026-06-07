const form = document.querySelector('#prediction-form');
const statusBox = document.querySelector('#status');
const results = document.querySelector('#results');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  setStatus('Consultando Gemini y ejecutando simulación Monte Carlo...', false);
  results.classList.add('hidden');
  const payload = {
    local: document.querySelector('#home').value,
    visitante: document.querySelector('#away').value,
    simulations: Number(document.querySelector('#simulations').value || 20000),
    force_refresh: document.querySelector('#force-refresh').checked,
  };
  try {
    const response = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Error desconocido');
    render(data);
    setStatus(data.cached ? 'Resultado reutilizado desde caché local de 24 horas.' : 'Predicción generada con datos nuevos de Gemini.', false);
  } catch (error) {
    setStatus(error.message, true);
  }
});

function setStatus(message, isError) {
  statusBox.textContent = message;
  statusBox.classList.toggle('hidden', false);
  statusBox.classList.toggle('error', isError);
}

function render(data) {
  results.classList.remove('hidden');
  renderProbabilities(data);
  renderExpectedGoals(data.simulation.expected_goals);
  renderTopScores(data.simulation.top_scores);
  renderRatings(data.ratings);
  renderInfluences(data.group_influence_percentages);
  renderExplanation(data.explanation);
  renderStats(data.match);
}

function renderProbabilities(data) {
  const home = data.match.local.nombre;
  const away = data.match.visitante.nombre;
  const sim = data.simulation;
  document.querySelector('#probabilities').innerHTML = [
    [home, sim.home_win_probability],
    ['Empate', sim.draw_probability],
    [away, sim.away_win_probability],
  ].map(([label, value]) => `<div class="prob-card"><span>${label}</span><strong>${value}%</strong></div>`).join('');
}

function renderExpectedGoals(goals) {
  document.querySelector('#expected-goals').innerHTML = Object.entries(goals)
    .map(([team, value]) => `<p><strong>${team}</strong>: ${value}</p>`).join('');
}

function renderTopScores(scores) {
  document.querySelector('#top-scores').innerHTML = scores
    .map(item => `<li><strong>${item.score}</strong> · ${item.probability}% (${item.count})</li>`).join('');
}

function renderRatings(ratings) {
  const labels = { offensive:'Ataque', defensive:'Defensa', midfield:'Mediocampo', goalkeeper:'Arquero', squad:'Plantel', recent_form:'Forma', global_score:'Global' };
  document.querySelector('#ratings').innerHTML = Object.entries(ratings).map(([side, rating]) => {
    const rows = Object.entries(labels).map(([key, label]) => {
      const value = rating[key];
      return `<div><strong>${label}</strong> ${value}<div class="bar"><span style="width:${Math.max(0, Math.min(100, value))}%"></span></div></div>`;
    }).join('');
    return `<div class="rating-card"><h3>${side === 'local' ? 'Local' : 'Visitante'}</h3>${rows}</div>`;
  }).join('');
}

function renderInfluences(influences) {
  document.querySelector('#influences').innerHTML = Object.entries(influences)
    .map(([group, pct]) => `<span class="chip">${group}: ${pct}%</span>`).join('');
}

function renderExplanation(explanation) {
  document.querySelector('#explanation').innerHTML = `
    <h3>Favorece al local</h3><ul>${listItems(explanation.factores_local)}</ul>
    <h3>Favorece al visitante</h3><ul>${listItems(explanation.factores_visitante)}</ul>
    <h3>Diferencias clave</h3><pre>${escapeHtml(JSON.stringify(explanation.diferencias_clave, null, 2))}</pre>
    <h3>Lesiones y suspensiones</h3><pre>${escapeHtml(JSON.stringify(explanation.lesiones_importantes, null, 2))}</pre>
    <p>${escapeHtml(explanation.impacto_localia)}</p>
    <p><strong>${escapeHtml(explanation.lectura_probabilidades)}</strong></p>`;
}

function renderStats(match) {
  const rows = [];
  for (const team of [match.local, match.visitante]) {
    for (const [group, stats] of Object.entries(team.estadisticas)) {
      for (const [key, stat] of Object.entries(stats)) {
        rows.push(`<tr><td>${escapeHtml(team.nombre)}</td><td>${group}</td><td>${key}</td><td>${stat.valor ?? 'null'}</td><td>${escapeHtml(stat.fuente)}</td><td class="${stat.confianza.toLowerCase()}">${stat.confianza}</td></tr>`);
      }
    }
  }
  document.querySelector('#stats-table').innerHTML = `<table><thead><tr><th>Equipo</th><th>Grupo</th><th>Variable</th><th>Valor</th><th>Fuente</th><th>Confianza</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
}

function listItems(items) {
  if (!items || !items.length) return '<li>Sin ventaja clara detectada.</li>';
  return items.map(item => `<li>${escapeHtml(item)}</li>`).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}
