const assert = require('node:assert');
const S = require('../scoring.js');
require('../data.js');
const D = globalThis.LSData;

const icp = {
  id: 'i', version: 1, cnaes: ['6201-5/00'], ufs: ['CE'], portes: ['ME'], minAge: 2, minCapital: 50000,
  weights: { cnae: 30, uf: 20, porte: 15, idade: 10, capital: 15, contato: 10 }
};
const base = {
  cnpj: '00.000.001/0001-00', cnae: '6201-5/00', cnaeDesc: 'x', uf: 'CE', cidade: 'Fortaleza', porte: 'ME',
  abertura: '2015-01-15', situacao: 'Ativa', capital: 80000, email: 'a@b.example', telefone: null
};

// Aderência total
assert.strictEqual(S.evaluate(base, icp).score, 100);
// Determinismo
assert.deepStrictEqual(S.evaluate(base, icp), S.evaluate(base, icp));
// Critério obrigatório elimina
const baixada = S.evaluate({ ...base, situacao: 'Baixada' }, icp);
assert.strictEqual(baixada.score, 0);
assert.strictEqual(baixada.eligible, false);
// Dado ausente: não conta pontos e é sinalizado
const sem = S.evaluate({ ...base, capital: null }, icp);
assert.strictEqual(sem.score, 85);
assert.strictEqual(sem.unknownCount, 1);
assert.strictEqual(sem.criteria.find(c => c.key === 'capital').status, 'unknown');
// Versão do ICP registrada
assert.strictEqual(S.evaluate(base, { ...icp, version: 7 }).icpVersion, 7);
// Dados sintéticos: 40 empresas, CNPJs únicos
assert.strictEqual(D.COMPANIES.length, 40);
assert.strictEqual(new Set(D.COMPANIES.map(c => c.cnpj)).size, 40);
// Scores sempre entre 0 e 100
D.COMPANIES.forEach(c => { const s = S.evaluate(c, icp).score; assert.ok(s >= 0 && s <= 100); });

console.log('OK: todos os testes passaram');
