(function () {
  var D = window.LSData, S = window.LSScoring;
  var TODAY = '2026-11-01'; 
  var STAGES = ['Novo', 'Contato', 'Reunião', 'Proposta', 'Ganho', 'Perdido'];
  var OPEN = ['Novo', 'Contato', 'Reunião', 'Proposta'];
  var OWNERS = ['Ana', 'Bruno', 'Carla'];
  var KEY = 'leads-search-demo-v1';
  var remote = false;       
  var cache = {};           
  var timer = null;

  function h(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }
  function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 86400000); }
  function offset(days) { var d = new Date(TODAY); d.setUTCDate(d.getUTCDate() - days); return d.toISOString().slice(0, 10); }
  function byCnpj(c) { return (cache[c] && cache[c].c) || D.COMPANIES.filter(function (x) { return x.cnpj === c; })[0]; }

  /* ---------- Estado ---------- */
  function seed() {
    var icp = {
      id: 'icp1', name: 'Software e TI no Nordeste', version: 1,
      cnaes: ['6201-5/00', '6204-0/00'], ufs: ['CE', 'PE', 'BA', 'RN'],
      portes: ['ME', 'EPP', 'Médio'], minAge: 2, minCapital: 50000,
      weights: { cnae: 30, uf: 20, porte: 15, idade: 10, capital: 15, contato: 10 }
    };
    var cs = D.COMPANIES;
    function deal(i, stage, owner, idle, note) {
      var c = cs[i];
      return { id: 'd' + i, cnpj: c.cnpj, nome: c.nome, stage: stage, owner: owner, origin: 'Carga inicial da demo',
        icpId: null, icpVersion: null, score: null, created: offset(idle + 10), lastActivity: offset(idle), notes: [note] };
    }
    return {
      icps: [icp], activeIcp: 'icp1', decisions: {}, tasks: [], events: [], suggestionDecisions: {},
      settings: { idleDays: 5 }, tab: 'search',
      deals: [
        deal(0, 'Novo', 'Ana', 6, 'Lead importado, ainda sem contato.'),
        deal(1, 'Contato', 'Bruno', 8, 'Primeiro contato por e-mail, sem resposta.'),
        deal(2, 'Reunião', 'Carla', 2, 'Reunião de descoberta realizada.'),
        deal(3, 'Proposta', 'Ana', 11, 'Proposta enviada, aguardando retorno.'),
        deal(4, 'Contato', 'Carla', 1, 'Ligação feita ontem.'),
        deal(5, 'Ganho', 'Bruno', 20, 'Contrato assinado.')
      ]
    };
  }
  var state;
  try { state = JSON.parse(localStorage.getItem(KEY)); } catch (e) { state = null; }
  if (!state || !state.icps) state = seed();
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* sem persistência */ } }
  function log(type, data) { state.events.push(Object.assign({ type: type, ts: TODAY }, data || {})); }
  function icp() { return state.icps.filter(function (i) { return i.id === state.activeIcp; })[0]; }

  var ui = { editing: false, minScore: 0, q: '', selected: {}, flash: null, expanded: {}, rows: null, total: 0 };

  /* ---------- Ações ---------- */
  function addToCrm(cnpjs, owner) {
    var cur = icp(), results = [], seen = {};
    cnpjs.forEach(function (c) {
      var key = S.digits(c), comp = byCnpj(c);
      var dup = seen[key] || state.deals.some(function (d) { return S.digits(d.cnpj) === key; });
      if (dup) { results.push({ nome: comp.nome, ok: false, msg: 'já está no CRM (deduplicado)' }); return; }
      seen[key] = true;
      var ev = (remote && cache[c]) ? cache[c].ev : S.evaluate(comp, cur);
      state.deals.push({ id: 'd' + key, cnpj: comp.cnpj, nome: comp.nome, stage: 'Novo', owner: owner,
        origin: 'Busca · ' + cur.name + ' v' + cur.version, icpId: cur.id, icpVersion: cur.version,
        score: ev.score, created: TODAY, lastActivity: TODAY, notes: ['Adicionado a partir da busca (score ' + ev.score + ').'] });
      state.decisions[c] = 'accepted';
      log('rec_accepted', { cnpj: c });
      results.push({ nome: comp.nome, ok: true, msg: 'adicionado para ' + owner });
    });
    ui.flash = results; ui.selected = {};
  }

  function suggestionFor(d) {
    var idle = daysBetween(d.lastActivity, TODAY), last = d.notes[d.notes.length - 1];
    var map = {
      Novo: ['Fazer o primeiro contato', 'Olá! Vi que a ' + d.nome + ' atua no segmento que atendemos. Posso te apresentar rapidamente como ajudamos empresas como a sua?'],
      Contato: ['Novo follow-up com outro ângulo', 'Olá! Retomando nosso contato: preparei um exemplo prático para a ' + d.nome + '. Faz sentido conversarmos 15 minutos?'],
      'Reunião': ['Enviar resumo e próximos passos', 'Obrigado pela conversa! Segue um resumo do que alinhamos e a sugestão de próximos passos para a ' + d.nome + '.'],
      Proposta: ['Cobrar retorno da proposta', 'Olá! Gostaria de saber se teve a chance de avaliar a proposta e se posso esclarecer alguma dúvida.']
    };
    return { dealId: d.id, key: d.id + '@' + d.lastActivity, title: map[d.stage][0], draft: map[d.stage][1],
      why: 'Estágio "' + d.stage + '" sem atividade há ' + idle + ' dias (limite: ' + state.settings.idleDays + '). Última nota: "' + last + '"' };
  }
  function suggestions() {
    return state.deals.filter(function (d) {
      return OPEN.indexOf(d.stage) >= 0 && daysBetween(d.lastActivity, TODAY) >= state.settings.idleDays;
    }).map(suggestionFor);
  }

  /* ---------- Views ---------- */
  function chips(name, options, selected, labels) {
    return options.map(function (o) {
      return '<label class="chip"><input type="checkbox" name="' + name + '" value="' + h(o) + '"' +
        (selected.indexOf(o) >= 0 ? ' checked' : '') + '><span>' + h(labels ? labels[o] : o) + '</span></label>';
    }).join('');
  }

  function viewSearch() {
    var cur = icp();
    var cnaeLabels = {}; D.CNAES.forEach(function (c) { cnaeLabels[c.code] = c.code + ' ' + c.desc; });
    var head = '<div class="card"><div class="row"><div><label class="lbl">Perfil de cliente ideal (ICP)</label>' +
      '<select data-change="icp">' + state.icps.map(function (i) {
        return '<option value="' + i.id + '"' + (i.id === cur.id ? ' selected' : '') + '>' + h(i.name) + ' (v' + i.version + ')</option>';
      }).join('') + '</select></div>' +
      '<div class="grow"></div><button data-action="icp-edit">' + (ui.editing ? 'Fechar editor' : 'Editar ICP') + '</button>' +
      '<button data-action="icp-dup">Duplicar</button></div>';
    if (ui.editing) {
      head += '<form data-form="icp" class="icp-form">' +
        '<label class="lbl">Nome</label><input name="name" value="' + h(cur.name) + '">' +
        '<label class="lbl">Atividades (CNAE)</label><div class="chips">' + chips('cnaes', D.CNAES.map(function (c) { return c.code; }), cur.cnaes, cnaeLabels) + '</div>' +
        '<label class="lbl">UFs</label><div class="chips">' + chips('ufs', D.UFS, cur.ufs) + '</div>' +
        '<label class="lbl">Portes</label><div class="chips">' + chips('portes', D.PORTES, cur.portes) + '</div>' +
        '<div class="row"><div><label class="lbl">Idade mínima (anos)</label><input type="number" name="minAge" min="0" value="' + cur.minAge + '"></div>' +
        '<div><label class="lbl">Capital social mínimo (R$)</label><input type="number" name="minCapital" min="0" step="1000" value="' + cur.minCapital + '"></div></div>' +
        '<p class="hint">Situação cadastral "Ativa" é obrigatória. Salvar cria uma nova versão do ICP (v' + (cur.version + 1) + '); cada análise registra a versão usada.</p>' +
        '<button class="primary" type="submit">Salvar nova versão</button></form>';
    }
    head += '</div>';

    var rows = remote ? (ui.rows || []) : D.COMPANIES.map(function (c) { return { c: c, ev: S.evaluate(c, cur) }; })
      .filter(function (r) { return r.ev.score >= ui.minScore && (!ui.q || (r.c.nome + r.c.cnpj + r.c.cidade).toLowerCase().indexOf(ui.q.toLowerCase()) >= 0); })
      .sort(function (a, b) { return b.ev.score - a.ev.score || a.c.nome.localeCompare(b.c.nome); });
    if (remote && !ui.rows && !ui.loading) fetchRows();

    var toolbar = '<div class="card row"><div><label class="lbl">Buscar</label><input data-input="q" value="' + h(ui.q) + '" placeholder="Nome, CNPJ ou cidade"></div>' +
      '<div><label class="lbl">Score mínimo: ' + ui.minScore + '</label><input type="range" aria-label="Score mínimo" min="0" max="100" step="5" value="' + ui.minScore + '" data-input="minScore"></div>' +
      '<div class="grow"></div><div><label class="lbl">Vendedor</label><select id="owner">' + OWNERS.map(function (o) { return '<option>' + o + '</option>'; }).join('') + '</select></div>' +
      '<button class="primary" data-action="add-selected">Adicionar selecionados ao CRM</button></div>';

    var flash = '';
    if (ui.flash) {
      flash = '<div class="card flash" role="status"><b>Resultado por registro</b><ul>' + ui.flash.map(function (r) {
        return '<li class="' + (r.ok ? 'ok' : 'warn') + '">' + h(r.nome) + ': ' + h(r.msg) + '</li>'; }).join('') + '</ul></div>';
    }

    var table = '<div class="card"><p class="hint">' + (remote ? 'Mostrando ' + rows.length + ' de ' + ui.total + ' empresas (consulta SQL)' : rows.length + ' empresas') + ' · ordenadas por aderência ao ICP · score ≠ probabilidade de compra</p><div class="list">' +
      rows.map(function (r) {
        var c = r.c, ev = r.ev, dec = state.decisions[c.cnpj], inCrm = state.deals.some(function (d) { return d.cnpj === c.cnpj; });
        var open = ui.expanded[c.cnpj];
        var cls = ev.score >= 70 ? 'hi' : ev.score >= 40 ? 'mid' : 'lo';
        return '<div class="item">' +
          '<div class="irow"><input type="checkbox" data-sel="' + c.cnpj + '"' + (ui.selected[c.cnpj] ? ' checked' : '') + (inCrm ? ' disabled' : '') + '>' +
          '<div class="grow"><b>' + h(c.nome) + '</b> <span class="muted">' + h(c.cnpj) + ' · ' + h(c.cidade) + '/' + h(c.uf) + ' · ' + h(c.porte) + '</span>' +
          '<div class="muted">' + h(c.cnaeDesc) + '</div></div>' +
          (!ev.eligible ? '<span class="badge out">fora do ICP</span>' : '') +
          (ev.unknownCount ? '<span class="badge unk" title="Dados ausentes">' + ev.unknownCount + ' dado(s) ausente(s)</span>' : '') +
          '<div class="score ' + cls + '"><span>' + ev.score + '</span><i style="width:' + ev.score + '%"></i></div>' +
          '<button data-action="toggle" data-id="' + c.cnpj + '">' + (open ? 'Ocultar' : 'Por quê?') + '</button>' +
          (inCrm ? '<span class="badge ok">no CRM</span>' :
            dec === 'rejected' ? '<span class="badge out">rejeitado</span>' :
            '<button data-action="accept" data-id="' + c.cnpj + '">Aceitar</button><button data-action="reject" data-id="' + c.cnpj + '">Rejeitar</button>') +
          '</div>' +
          (open ? '<div class="why"><ul>' + ev.criteria.map(function (k) {
            var icon = k.status === 'met' ? '✓' : k.status === 'unmet' ? '✗' : '?';
            return '<li class="' + k.status + '"><b>' + icon + '</b> ' + h(k.label) + (k.weight ? ' <span class="muted">(' + k.weight + ' pts)</span>' : ' <span class="muted">(obrigatório)</span>') +
              ' — ' + h(k.detail) + '</li>'; }).join('') + '</ul>' +
            '<div class="muted">Fonte: ' + h(c.fonte) + ' · atualizado em ' + h(c.atualizado) + ' · ICP v' + ev.icpVersion + '</div></div>' : '') +
          '</div>';
      }).join('') + '</div></div>';
    return head + toolbar + flash + table;
  }

  function viewCrm() {
    return '<div class="kanban">' + STAGES.map(function (s) {
      var ds = state.deals.filter(function (d) { return d.stage === s; });
      return '<div class="col"><h3>' + s + ' <span class="muted">' + ds.length + '</span></h3>' + ds.map(function (d) {
        var idle = daysBetween(d.lastActivity, TODAY);
        return '<div class="deal"><b>' + h(d.nome) + '</b><div class="muted">' + h(d.owner) + ' · ' + h(d.origin) + '</div>' +
          (d.score != null ? '<div class="muted">Score na entrada: ' + d.score + ' (ICP v' + d.icpVersion + ')</div>' : '') +
          '<div class="muted">Última atividade: ' + idle + ' dia(s)</div>' +
          '<div class="muted note">' + h(d.notes[d.notes.length - 1]) + '</div>' +
          '<select data-move="' + d.id + '">' + STAGES.map(function (x) { return '<option' + (x === d.stage ? ' selected' : '') + '>' + x + '</option>'; }).join('') + '</select>' +
          '<button data-action="activity" data-id="' + d.id + '">Registrar atividade</button></div>';
      }).join('') + '</div>';
    }).join('') + '</div>';
  }

  function viewCopilot() {
    var sug = suggestions().filter(function (s) { return !state.suggestionDecisions[s.key]; });
    var out = '<div class="card row"><div><label class="lbl">Considerar parado após (dias): ' + state.settings.idleDays + '</label>' +
      '<input type="range" aria-label="Dias sem atividade" min="1" max="15" value="' + state.settings.idleDays + '" data-input="idle"></div>' +
      '<p class="hint grow">Sugestões determinísticas baseadas em estágio, tempo parado e notas. Nada é criado sem a sua aprovação. Os textos são rascunhos editáveis; aqui é o ponto onde um LLM pode refinar a redação.</p></div>';
    out += sug.length ? sug.map(function (s) {
      return '<div class="card"><b>' + h(s.title) + '</b> <span class="muted">· ' + h(state.deals.filter(function (d) { return d.id === s.dealId; })[0].nome) + '</span>' +
        '<p class="hint">Por quê: ' + h(s.why) + '</p>' +
        '<textarea data-draft="' + s.key + '">' + h(s.draft) + '</textarea>' +
        '<div class="row"><button class="primary" data-action="sug-accept" data-id="' + s.key + '">Aceitar e criar tarefa</button>' +
        '<button data-action="sug-dismiss" data-id="' + s.key + '">Descartar</button></div></div>';
    }).join('') : '<div class="card muted">Nenhuma oportunidade parada com o limite atual.</div>';
    out += '<div class="card"><b>Tarefas criadas (' + state.tasks.length + ')</b><ul>' + state.tasks.map(function (t) {
      return '<li>' + h(t.deal) + ': ' + h(t.title) + (t.edited ? ' <span class="badge unk">editada</span>' : '') + '</li>'; }).join('') + '</ul></div>';
    return out;
  }

  function viewMetrics() {
    var ev = state.events, n = function (t) { return ev.filter(function (e) { return e.type === t; }).length; };
    var recAcc = n('rec_accepted'), recRej = n('rec_rejected');
    var pending = D.COMPANIES.filter(function (c) { return !state.decisions[c.cnpj] && S.evaluate(c, icp()).score >= 70; }).length;
    var sugAcc = n('sug_accepted'), sugEd = n('sug_edited'), sugDis = n('sug_dismissed'), sugIgn = suggestions().filter(function (s) { return !state.suggestionDecisions[s.key]; }).length;
    var fromSearch = state.deals.filter(function (d) { return d.icpId; });
    var adv = fromSearch.filter(function (d) { return d.stage !== 'Novo'; }).length;
    function tile(v, l) { return '<div class="tile"><div class="big">' + v + '</div><div class="muted">' + l + '</div></div>'; }
    function pct(a, b) { return b ? Math.round(a / b * 100) + '%' : '—'; }
    return (remote ? analyticsHtml() : '') + '<div class="card"><b>Recomendações de leads (ICP)</b><div class="tiles">' +
      tile(recAcc, 'aceitas') + tile(recRej, 'rejeitadas') + tile(pending, 'score ≥ 70 sem decisão (ignoradas)') + tile(pct(recAcc, recAcc + recRej), 'taxa de aceitação') + '</div>' +
      '<p class="hint">Amostra: ' + (recAcc + recRej) + ' decisões.</p></div>' +
      '<div class="card"><b>CRM Copilot</b><div class="tiles">' + tile(sugAcc, 'aceitas') + tile(sugEd, 'editadas') + tile(sugDis, 'descartadas') + tile(sugIgn, 'pendentes') + '</div>' +
      '<p class="hint">Amostra: ' + (sugAcc + sugEd + sugDis) + ' decisões.</p></div>' +
      '<div class="card"><b>Funil dos leads vindos da busca</b><div class="tiles">' + tile(fromSearch.length, 'leads adicionados') + tile(adv, 'avançaram além de "Novo"') + tile(pct(adv, fromSearch.length), 'avanço') + '</div>' +
      '<p class="hint">Período: até ' + TODAY + ' (data de referência da demo). Esta métrica mostra correlação, não impacto causal comprovado. Com poucos dados fictícios, os números servem só para ilustrar o painel.</p></div>';
  }

  /* ---------- Modo API (FastAPI + SQLite) ---------- */
  function api(path, opts) {
    return fetch(path, opts).then(function (r) { if (!r.ok) throw new Error(path + ' ' + r.status); return r.json(); });
  }
  function fetchRows() {
    var cur = icp(); ui.loading = true;
    api('/api/search', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ icp: { id: cur.id, name: cur.name, version: cur.version, cnaes: cur.cnaes, ufs: cur.ufs,
        portes: cur.portes, minAge: cur.minAge, minCapital: cur.minCapital, weights: cur.weights },
        q: ui.q || null, min_score: ui.minScore, limit: 100 }) })
      .then(function (r) {
        ui.rows = r.rows.map(function (x) { cache[x.company.cnpj] = { c: x.company, ev: x.ev }; return { c: x.company, ev: x.ev }; });
        ui.total = r.total;
      }).catch(function () { ui.rows = []; }).then(function () { ui.loading = false; render(); });
  }
  function loadOnce(key, paths) {
    if (ui[key] || ui[key + 'Loading']) return;
    ui[key + 'Loading'] = true;
    Promise.all(paths.map(function (p) { return api(p).catch(function () { return null; }); }))
      .then(function (r) { ui[key] = r; ui[key + 'Loading'] = false; render(); });
  }
  function table(cols, rows) {
    return '<table><thead><tr>' + cols.map(function (c) { return '<th>' + h(c[1]) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      rows.map(function (r) { return '<tr>' + cols.map(function (c) { return '<td>' + h(r[c[0]] == null ? '—' : r[c[0]]) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>';
  }
  function analyticsHtml() {
    loadOnce('analytics', ['/api/metrics/funnel', '/api/metrics/sellers', '/api/metrics/score_bands', '/api/metrics/stage_time']);
    var a = ui.analytics; if (!a) return '<div class="card muted">Carregando métricas do SQLite…</div>';
    return '<div class="card"><b>Base analítica (SQL com CTEs e window functions)</b>' +
      '<p class="hint">Dados sintéticos: 1.500 deals e ~4.300 recomendações.</p>' +
      '<b>Funil</b>' + table([['stage', 'Estágio'], ['deals', 'Deals'], ['conv_etapa_anterior', '% vs. anterior'], ['conv_total', '% vs. topo']], a[0] || []) +
      '<b>Aceitação por vendedor</b>' + table([['ranking', '#'], ['vendedor', 'Vendedor'], ['aceitas', 'Aceitas'], ['rejeitadas', 'Rejeitadas'], ['ignoradas', 'Ignoradas'], ['taxa_aceitacao', '% aceitação']], a[1] || []) +
      '<b>Score na entrada × taxa de ganho</b> <span class="muted">(correlação, não causalidade)</span>' + table([['faixa', 'Faixa'], ['deals', 'Deals'], ['ganhos', 'Ganhos'], ['taxa_ganho', '% ganho']], a[2] || []) +
      '<b>Tempo médio por estágio</b>' + table([['stage', 'Estágio'], ['amostra', 'Amostra'], ['dias_medios', 'Dias']], a[3] || []) + '</div>';
  }
  function viewLookalike() {
    if (!remote) return '<div class="card muted">O módulo de empresas semelhantes (ML) requer a API. Rode <code>uvicorn backend.api:app</code>.</div>';
    loadOnce('lookalike', ['/api/lookalike?limit=30', '/api/model']);
    var L = ui.lookalike; if (!L) return '<div class="card muted">Carregando…</div>';
    var rows = L[0] || [], m = L[1];
    var head = '';
    if (m) {
      var lg = m.metrics.logistic, bl = m.metrics.icp_rules_baseline;
      head = '<div class="card"><b>Modelo lookalike (regressão logística)</b>' +
        '<p class="hint">' + h(m.note) + ' Validação: ' + h(m.validation) + '.</p><div class="tiles">' +
        '<div class="tile"><div class="big">' + lg.auc.toFixed(2) + '</div><div class="muted">AUC (regras do ICP: ' + bl.auc.toFixed(2) + ')</div></div>' +
        '<div class="tile"><div class="big">' + Math.round(lg['precision@100'] * 100) + '%</div><div class="muted">precision@100 (acaso: ' + (m.prevalence * 100).toFixed(1) + '%)</div></div>' +
        '<div class="tile"><div class="big">' + lg['lift@100'].toFixed(1) + '×</div><div class="muted">lift@100</div></div></div>' +
        '<p class="hint">Variáveis mais importantes (queda de AUC por permutação): ' +
        m.permutation_importance.slice(0, 4).map(function (p) { return h(p.feature) + ' (' + p.auc_drop.toFixed(3) + ')'; }).join(' · ') + '</p></div>';
    }
    return head + '<div class="card"><b>Empresas parecidas com os clientes conquistados</b><p class="hint">Probabilidade out-of-fold. Dados ausentes viram indicador no modelo.</p><div class="list">' +
      rows.map(function (r) {
        return '<div class="item"><div class="irow"><div class="grow"><b>' + h(r.nome) + '</b> <span class="muted">' + h(r.cnpj) + ' · ' + h(r.cidade) + '/' + h(r.uf) + ' · ' + h(r.porte) + '</span>' +
          '<div class="muted">' + h(r.cnae_desc) + '</div>' +
          '<div class="muted">Por quê: ' + r.reasons.map(function (x) { return h(x.feature); }).join(' · ') + '</div></div>' +
          '<div class="score hi"><span>' + (r.score * 100).toFixed(0) + '%</span><i style="width:' + Math.min(100, r.score * 100 * 3) + '%"></i></div></div></div>';
      }).join('') + '</div></div>';
  }

  /* ---------- Render e eventos ---------- */
  function render() {
    var views = { search: viewSearch, crm: viewCrm, copilot: viewCopilot, metrics: viewMetrics, lookalike: viewLookalike };
    document.querySelectorAll('nav button').forEach(function (button) {
      var current = button.dataset.tab === state.tab;
      button.classList.toggle('active', current);
      if (current) button.setAttribute('aria-current', 'true');
      else button.removeAttribute('aria-current');
    });
    var active = document.activeElement, id = active && active.getAttribute && active.getAttribute('data-input');
    var pos = active && active.selectionStart;
    document.getElementById('view').innerHTML = views[state.tab]();
    if (id) { var el = document.querySelector('[data-input="' + id + '"]'); if (el) { el.focus(); try { el.setSelectionRange(pos, pos); } catch (e) {} } }
    save();
  }

  document.querySelector('nav').addEventListener('click', function (e) {
    if (e.target.dataset.tab) { state.tab = e.target.dataset.tab; ui.flash = null; render(); }
  });
  document.getElementById('reset').addEventListener('click', function () { state = seed(); ui = { editing: false, minScore: 0, q: '', selected: {}, flash: null, expanded: {}, rows: null, total: 0 }; render(); });

  var view = document.getElementById('view');
  view.addEventListener('click', function (e) {
    var t = e.target, a = t.dataset.action, id = t.dataset.id;
    if (!a) return;
    var ownerEl = document.getElementById('owner'), owner = ownerEl ? ownerEl.value : OWNERS[0];
    if (a === 'toggle') ui.expanded[id] = !ui.expanded[id];
    else if (a === 'accept') addToCrm([id], owner);
    else if (a === 'reject') { state.decisions[id] = 'rejected'; log('rec_rejected', { cnpj: id }); }
    else if (a === 'add-selected') {
      var ids = Object.keys(ui.selected).filter(function (k) { return ui.selected[k]; });
      if (!ids.length) { ui.flash = [{ nome: 'Nenhuma empresa selecionada', ok: false, msg: 'marque ao menos uma' }]; } else addToCrm(ids, owner);
    }
    else if (a === 'icp-edit') ui.editing = !ui.editing;
    else if (a === 'icp-dup') {
      var cur = icp(), copy = JSON.parse(JSON.stringify(cur));
      copy.id = 'icp' + (state.icps.length + 1); copy.name = cur.name + ' (cópia)'; copy.version = 1;
      state.icps.push(copy); state.activeIcp = copy.id; ui.rows = null;
    }
    else if (a === 'activity') {
      var d = state.deals.filter(function (x) { return x.id === id; })[0];
      d.lastActivity = TODAY; d.notes.push('Atividade registrada manualmente.'); log('activity', { deal: id });
    }
    else if (a === 'sug-accept' || a === 'sug-dismiss') {
      var s = suggestions().filter(function (x) { return x.key === id; })[0];
      var ta = view.querySelector('textarea[data-draft="' + id + '"]');
      if (a === 'sug-accept') {
        var edited = ta.value !== s.draft, deal = state.deals.filter(function (x) { return x.id === s.dealId; })[0];
        state.tasks.push({ deal: deal.nome, title: s.title + ' — ' + ta.value, edited: edited });
        state.suggestionDecisions[id] = edited ? 'edited' : 'accepted'; log(edited ? 'sug_edited' : 'sug_accepted', { deal: s.dealId });
      } else { state.suggestionDecisions[id] = 'dismissed'; log('sug_dismissed', { deal: s.dealId }); }
    }
    render();
  });
  view.addEventListener('change', function (e) {
    var t = e.target;
    if (t.dataset.change === 'icp') { state.activeIcp = t.value; ui.rows = null; }
    else if (t.dataset.sel) { ui.selected[t.dataset.sel] = t.checked; return; }
    else if (t.dataset.move) {
      var d = state.deals.filter(function (x) { return x.id === t.dataset.move; })[0];
      d.notes.push('Movido de ' + d.stage + ' para ' + t.value + '.'); d.stage = t.value; d.lastActivity = TODAY; log('moved', { deal: d.id, to: t.value });
    } else return;
    render();
  });
  view.addEventListener('input', function (e) {
    var t = e.target, k = t.dataset.input;
    if (k === 'q') ui.q = t.value; else if (k === 'minScore') ui.minScore = +t.value; else if (k === 'idle') state.settings.idleDays = +t.value; else return;
    if (remote && (k === 'q' || k === 'minScore')) { clearTimeout(timer); timer = setTimeout(function () { ui.rows = null; ui.loading = false; fetchRows(); }, 250); return; }
    render();
  });
  view.addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target, cur = icp(), fd = new FormData(f);
    cur.name = fd.get('name') || cur.name;
    cur.cnaes = fd.getAll('cnaes'); cur.ufs = fd.getAll('ufs'); cur.portes = fd.getAll('portes');
    cur.minAge = +fd.get('minAge') || 0; cur.minCapital = +fd.get('minCapital') || 0;
    cur.version += 1; ui.editing = false; ui.rows = null; log('icp_saved', { icp: cur.id, version: cur.version });
    render();
  });

  render();
  if (/^https?:/.test(location.protocol)) {
    api('/api/health').then(function (j) {
      remote = true; ui.rows = null;
      document.getElementById('mode').textContent = 'API + SQLite · ' + j.companies.toLocaleString('pt-BR') + ' empresas';
      document.querySelector('[data-tab="lookalike"]').hidden = false;
      render();
    }).catch(function () { /* sem API: modo estático */ });
  }
})();
