/*
 * Motor de scoring determinístico e explicável.
 * Mesma empresa + mesmo ICP (mesma versão) => mesma pontuação.
 * O score mede ADERÊNCIA ao ICP, não probabilidade de compra.
 */
(function (root) {
  // Data de referência fixa: torna a demo reproduzível.
  var REF_DATE = new Date('2026-11-01T00:00:00Z');

  function ageYears(isoDate) {
    if (!isoDate) return null;
    var d = new Date(isoDate + 'T00:00:00Z');
    return (REF_DATE - d) / (365.25 * 24 * 3600 * 1000);
  }

  function digits(s) { return String(s || '').replace(/\D/g, ''); }

  function evaluate(c, icp) {
    var w = icp.weights;
    var criteria = [];
    function add(key, label, weight, status, detail, required) {
      criteria.push({ key: key, label: label, weight: weight, status: status, detail: detail, required: !!required });
    }

    // Critério obrigatório (eliminatório)
    add('situacao', 'Situação cadastral ativa', 0,
      c.situacao == null ? 'unknown' : (c.situacao === 'Ativa' ? 'met' : 'unmet'),
      c.situacao == null ? 'Situação não informada' : 'Situação: ' + c.situacao, true);

    add('cnae', 'Atividade (CNAE) desejada', w.cnae,
      c.cnae == null ? 'unknown' : (icp.cnaes.indexOf(c.cnae) >= 0 ? 'met' : 'unmet'),
      c.cnae == null ? 'CNAE não informado' : c.cnae + ' · ' + c.cnaeDesc);

    add('uf', 'Região (UF) desejada', w.uf,
      c.uf == null ? 'unknown' : (icp.ufs.indexOf(c.uf) >= 0 ? 'met' : 'unmet'),
      c.uf == null ? 'UF não informada' : c.cidade + '/' + c.uf);

    add('porte', 'Porte desejado', w.porte,
      c.porte == null ? 'unknown' : (icp.portes.indexOf(c.porte) >= 0 ? 'met' : 'unmet'),
      c.porte == null ? 'Porte não informado' : 'Porte: ' + c.porte);

    var age = ageYears(c.abertura);
    add('idade', 'Idade mínima (' + icp.minAge + ' anos)', w.idade,
      age == null ? 'unknown' : (age >= icp.minAge ? 'met' : 'unmet'),
      age == null ? 'Data de abertura não informada' : 'Aberta há ' + age.toFixed(1) + ' anos');

    add('capital', 'Capital social mínimo', w.capital,
      c.capital == null ? 'unknown' : (c.capital >= icp.minCapital ? 'met' : 'unmet'),
      c.capital == null ? 'Capital social não informado' : 'Capital: R$ ' + c.capital.toLocaleString('pt-BR'));

    add('contato', 'Possui contato disponível', w.contato,
      (c.email || c.telefone) ? 'met' : 'unmet',
      (c.email || c.telefone) ? 'Contato na base' : 'Sem e-mail ou telefone');

    var total = 0, earned = 0, unknown = 0;
    criteria.forEach(function (k) {
      total += k.weight;
      if (k.status === 'met') earned += k.weight;
      if (k.status === 'unknown') unknown++;
    });
    var required = criteria.filter(function (k) { return k.required; });
    var eligible = required.every(function (k) { return k.status === 'met'; });
    var score = !eligible || total === 0 ? 0 : Math.round((earned / total) * 100);

    return {
      cnpj: c.cnpj, score: score, eligible: eligible, criteria: criteria,
      unknownCount: unknown, icpId: icp.id, icpVersion: icp.version
    };
  }

  var api = { evaluate: evaluate, ageYears: ageYears, digits: digits, REF_DATE: REF_DATE };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.LSScoring = api;
})(typeof window !== 'undefined' ? window : globalThis);
