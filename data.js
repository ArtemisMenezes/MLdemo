/*
 * DADOS 100% FICTÍCIOS, gerados de forma determinística (PRNG com semente fixa).
 * Nomes inventados e CNPJs com dígitos verificadores inválidos de propósito
 * (formato 00.000.NNN/0001-00), para não coincidirem com empresas reais.
 */
(function (root) {
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var rnd = mulberry32(20261104);
  function pick(arr) { return arr[Math.floor(rnd() * arr.length)]; }

  var CNAES = [
    { code: '6201-5/00', desc: 'Desenvolvimento de software sob encomenda', tag: 'Soft' },
    { code: '6204-0/00', desc: 'Consultoria em tecnologia da informação', tag: 'Tech' },
    { code: '7020-4/00', desc: 'Consultoria em gestão empresarial', tag: 'Gestão' },
    { code: '7311-4/00', desc: 'Agências de publicidade', tag: 'Mkt' },
    { code: '8630-5/04', desc: 'Atividade odontológica', tag: 'Odonto' },
    { code: '4120-4/00', desc: 'Construção de edifícios', tag: 'Obras' },
    { code: '5611-2/01', desc: 'Restaurantes e similares', tag: 'Food' },
    { code: '8599-6/04', desc: 'Treinamento em desenvolvimento profissional', tag: 'Edu' }
  ];
  var CITIES = {
    CE: ['Fortaleza', 'Sobral', 'Juazeiro do Norte'], PE: ['Recife', 'Olinda', 'Caruaru'],
    BA: ['Salvador', 'Feira de Santana'], RN: ['Natal', 'Mossoró'],
    SP: ['São Paulo', 'Campinas'], MG: ['Belo Horizonte', 'Uberlândia'], RS: ['Porto Alegre', 'Caxias do Sul']
  };
  var UFS = Object.keys(CITIES);
  var A = ['Aurora', 'Vértice', 'Nimbus', 'Atlas', 'Brisa', 'Cobalto', 'Delta', 'Eclipse', 'Faísca', 'Girassol',
           'Horizonte', 'Ícaro', 'Jangada', 'Kappa', 'Lumen', 'Mandacaru', 'Névoa', 'Órbita', 'Prisma', 'Quasar'];
  var B = ['Digital', 'Soluções', 'Sistemas', 'Consultoria', 'Serviços', 'Labs', 'Group', 'Tecnologia', 'Partners', 'Studio'];
  var PORTES = ['MEI', 'ME', 'ME', 'EPP', 'EPP', 'Médio', 'Grande'];

  var list = [];
  for (var i = 1; i <= 40; i++) {
    var cnae = pick(CNAES);
    var uf = rnd() < 0.6 ? pick(['CE', 'PE', 'BA', 'RN']) : pick(UFS);
    var year = 2000 + Math.floor(rnd() * 25);
    var month = 1 + Math.floor(rnd() * 12);
    var situacao = rnd() < 0.85 ? 'Ativa' : pick(['Baixada', 'Suspensa']);
    var porte = pick(PORTES);
    var capBase = { MEI: 6000, ME: 30000, EPP: 120000, 'Médio': 600000, Grande: 3000000 }[porte];
    var n = String(i).padStart(3, '0');
    var c = {
      cnpj: '00.000.' + n + '/0001-00',
      nome: pick(A) + ' ' + pick(B) + ' ' + n,
      cnae: cnae.code, cnaeDesc: cnae.desc,
      uf: uf, cidade: pick(CITIES[uf]),
      porte: porte,
      abertura: year + '-' + String(month).padStart(2, '0') + '-15',
      situacao: situacao,
      capital: Math.round(capBase * (0.5 + rnd())),
      email: 'contato@empresa' + n + '.example',
      telefone: '(00) 00000-' + String(1000 + i),
      atualizado: '2026-10-' + String(1 + Math.floor(rnd() * 28)).padStart(2, '0'),
      fonte: 'Base demo (sintética)'
    };
    if (rnd() < 0.15) c.capital = null;
    if (rnd() < 0.10) c.abertura = null;
    if (rnd() < 0.20) c.email = null;
    if (rnd() < 0.25) c.telefone = null;
    list.push(c);
  }

  root.LSData = { COMPANIES: list, CNAES: CNAES, UFS: ['CE', 'PE', 'BA', 'RN', 'PB', 'MA', 'SP', 'RJ', 'MG', 'RS', 'PR', 'SC'], PORTES: ['MEI', 'ME', 'EPP', 'Médio', 'Grande'] };
})(typeof window !== 'undefined' ? window : globalThis);
