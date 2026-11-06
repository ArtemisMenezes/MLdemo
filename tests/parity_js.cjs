// Lê {companies, icp} do stdin e imprime {cnpj: score} usando o scoring.js do front.
const S = require('../scoring.js');
let buf = '';
process.stdin.on('data', d => (buf += d)).on('end', () => {
  const { companies, icp } = JSON.parse(buf);
  const out = {};
  companies.forEach(c => { out[c.cnpj] = S.evaluate({ ...c, cnaeDesc: c.cnae_desc }, icp).score; });
  console.log(JSON.stringify(out));
});
