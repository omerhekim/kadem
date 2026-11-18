'use strict';
/* KADEM – arayüz. Sunucu (Python) tek doğruluk kaynağıdır; her işlemden sonra güncel durum gelir. */

const TOKEN = new URLSearchParams(location.hash.slice(1)).get('t') || '';
let S = null;                 // sunucu durumu
const UI = {
  sayfa: 'dosyalar',
  secili: new Set(),          // toplu işlem için seçili dosya satırları (yol)
  sonSecili: null,            // Shift ile aralık seçimi için son tıklanan satır
  yanDar: null,               // yan menü: null = pencere genişliğine göre, true/false = kullanıcı seçimi
  dosyaFiltre: '',
  b: null,                    // sorgu oluşturucu durumu
  sonucSekme: 'uyarilar',
  uyariFiltre: { Hata: true, 'Uyarı': true, Bilgi: false, ara: '' },
  dongulerHasta: '',
  yoklaniyor: false,
};

/* ------------------------------------------------------------------ yardımcılar */
function koy(el, ...kids) {
  el.replaceChildren(...kids.flat(Infinity).filter(k => k !== null && k !== undefined && k !== false)
    .map(k => k instanceof Node ? k : document.createTextNode(String(k))));
  return el;
}
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  let deger;
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'value') deger = v;
    else if (k === 'checked') el.checked = !!v;
    else if (k === 'html') el.innerHTML = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  if (deger !== undefined) el.value = deger;
  return el;
}

const IKONLAR = {
  klasor: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  dosya: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5',
  arti: 'M12 5v14M5 12h14',
  cop: 'M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3',
  yukari: 'M12 19V5M6 11l6-6 6 6',
  asagi: 'M12 5v14M6 13l6 6 6-6',
  kalem: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  oynat: 'M7 5l12 7-12 7z',
  kaydet: 'M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM7 3v6h8V3M7 21v-7h10v7',
  ac: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H7l-4 9z',
  yeni: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM12 11v6M9 14h6',
  tamam: 'M5 12l5 5 9-11',
  uyari: 'M12 3l10 18H2zM12 10v5M12 18h.01',
  bilgi: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 8h.01',
  kapat: 'M6 6l12 12M18 6L6 18',
  yenile: 'M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6',
  disari: 'M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4',
  sablon: 'M4 5h16M4 12h10M4 19h7',
  ust: 'M15 18l-6-6 6-6',
  surucu: 'M3 7h18v10H3zM7 12h.01',
  ev: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  kopya: 'M9 9h11v12H9zM5 15V3h11',
  yapistir: 'M9 4h6v3H9zM9 5H6v16h12V5h-3M9 12h6M9 16h6',
  daralt: 'M15 6l-6 6 6 6',
  genislet: 'M9 6l6 6-6 6',
  dil: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
};
function ikon(ad, cls) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('class', 'ikon ' + (cls || ''));
  s.setAttribute('fill', 'none'); s.setAttribute('stroke', 'currentColor'); s.setAttribute('stroke-width', '1.9');
  s.setAttribute('stroke-linecap', 'round'); s.setAttribute('stroke-linejoin', 'round'); s.setAttribute('aria-hidden', 'true');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', IKONLAR[ad] || ''); s.append(p);
  return s;
}
function btn(yazi, tikla, o = {}) {
  return h('button', { class: 'btn ' + (o.cls || ''), onclick: tikla, disabled: o.disabled, title: o.title, type: 'button',
    'aria-label': o.aria }, o.ikon ? ikon(o.ikon) : null, yazi);
}
function sec(secenekler, deger, degisti, o = {}) {
  const el = h('select', { onchange: (e) => degisti(e.target.value), disabled: o.disabled, 'aria-label': o.aria, class: o.cls,
    style: o.style });
  for (const s of secenekler) {
    if (s.grup) {
      const og = h('optgroup', { label: s.grup });
      for (const x of s.secenekler) og.append(h('option', { value: x.v, disabled: x.disabled }, x.t));
      el.append(og);
    } else el.append(h('option', { value: s.v, disabled: s.disabled }, s.t));
  }
  el.value = deger == null ? '' : deger;
  return el;
}
function bildir(metin, tur = '') {
  const el = h('div', { class: 'bildirim ' + tur, role: 'status' }, metin);
  document.getElementById('bildirimler').append(el);
  setTimeout(() => el.remove(), tur === 'hata' ? 9000 : 4500);
}
const fmt = (v, n = 2) => (v === null || v === undefined || Number.isNaN(v)) ? '' :
  (typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(n)) : String(v));
const TARAF = { L: 'Sol', R: 'Sağ' };

/* ------------------------------------------------------------------ dil (English) */
// Arayüz Türkçe yazılır; İngilizce seçiliyse ekrana gelen her metin sunucudaki sözlükle (ceviri_en.py) çevrilir.
const CEV = { aktif: false, tam: {}, desen: [], bellek: new Map(), gozlemci: null };
function cevir(s) {
  if (!CEV.aktif || typeof s !== 'string' || !s.trim()) return s;
  const b = CEV.bellek.get(s);
  if (b !== undefined) return b;
  let r = CEV.tam[s];
  if (r === undefined) {
    const k = s.trim();
    if (k !== s && CEV.tam[k] !== undefined) r = s.replace(k, CEV.tam[k]);
  }
  if (r === undefined) {
    r = s;
    for (const [rx, en, sira] of CEV.desen) {
      const m = rx.exec(s);
      if (!m) continue;
      const deg = [];
      sira.forEach((n, j) => { deg[n] = m[j + 1]; });
      r = en.replace(/\{(t?)(\d+)\}/g, (_, t, i) => { const v = deg[Number(i)] ?? ''; return t ? cevir(v) : v; });
      break;
    }
  }
  if (CEV.bellek.size < 20000) CEV.bellek.set(s, r);
  return r;
}
function cevirMetin(n) {
  if (n.parentElement && n.parentElement.closest('[translate="no"]')) return;   // adlar, dosya adları, program adı
  const v = n.nodeValue, c = cevir(v);
  if (c !== v) n.nodeValue = c;
}
function cevirOzn(el) {
  for (const a of ['title', 'placeholder', 'label', 'aria-label']) {
    const v = el.getAttribute && el.getAttribute(a);
    if (v) { const c = cevir(v); if (c !== v) el.setAttribute(a, c); }
  }
}
function cevirDugum(kok) {
  if (kok.nodeType === 3) return cevirMetin(kok);
  if (kok.nodeType !== 1) return;
  const tw = document.createTreeWalker(kok, NodeFilter.SHOW_TEXT);
  let n; while ((n = tw.nextNode())) cevirMetin(n);
  cevirOzn(kok);
  kok.querySelectorAll('[title],[placeholder],[label],[aria-label]').forEach(cevirOzn);
}
async function dilHazirla() {
  if (S?.dil !== 'en') return;
  try {
    const t = await api('ceviri');
    CEV.tam = t.tam;
    CEV.desen = t.desen.map(([k, en, sira]) => [new RegExp(k), en, sira]);
    CEV.aktif = true;
  } catch (e) { return; }
  document.documentElement.lang = 'en';
  document.title = cevir(document.title);
  cevirDugum(document.body);
  CEV.gozlemci = new MutationObserver(mlar => {
    for (const m of mlar) {
      if (m.type === 'childList') m.addedNodes.forEach(cevirDugum);
      else if (m.type === 'characterData') cevirMetin(m.target);
      else if (m.type === 'attributes') cevirOzn(m.target);
    }
  });
  CEV.gozlemci.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true,
    attributeFilter: ['title', 'placeholder', 'label', 'aria-label'] });
}
async function dilDegistir(d) {
  if (d === S.dil) return;
  await api('dil', { dil: d });
  UI.dilYukleniyor = true;
  location.reload();
}

/* ------------------------------------------------------------------ API */
async function api(ad, govde = {}) {
  let r;
  try {
    r = await fetch('/api/' + ad, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Token': TOKEN },
      body: JSON.stringify(govde) });
  } catch (e) {
    bildir('Programa ulaşılamıyor. Pencereyi kapatıp programı yeniden başlatın.', 'hata');
    throw e;
  }
  const j = await r.json();
  if (!j.ok) {
    if (!j.yerel_yok) bildir(j.hata || 'Bilinmeyen hata', 'hata');
    const e = new Error(j.hata || 'hata'); e.yanit = j; throw e;
  }
  return j;
}
async function islem(ad, govde = {}, o = {}) {
  const j = await api(ad, govde);
  if (j.dosyalar) { S = j; render(); }
  if (j.bilgi) bildir(j.bilgi, 'ok');
  if (S && S.is && S.is.calisiyor) yokla();
  return j;
}
async function yokla() {
  if (UI.yoklaniyor) return;
  UI.yoklaniyor = true;
  const onceki = UI.sayfa;
  try {
    while (true) {
      await new Promise(r => setTimeout(r, 600));
      const j = await api('ping');
      if (S) S.is = j.is;
      renderIs();
      if (!j.is.calisiyor) break;
    }
    S = await api('durum');
    if (S.is.hata) bildir(S.is.hata, 'hata');
    else if (S.is.tur === 'calistir') { bildir('Excel dosyası yazıldı.', 'ok'); if (UI.sayfa === onceki) UI.sonucSekme = UI.sonucSekme || 'uyarilar'; }
    else if (S.is.tur === 'tarama') bildir('Dosyalar tarandı.', 'ok');
    render();
  } finally { UI.yoklaniyor = false; }
}
// Pencere açık olduğu sürece sunucuya düzenli sinyal: program, sinyal kesilince pencerenin kapandığını anlar
setInterval(() => { if (!UI.yoklaniyor) api('ping').catch(() => {}); }, 10000);

/* ------------------------------------------------------------------ modal */
function modal({ baslik, govde, butonlar = [], genis = false, kapaninca }) {
  const kok = document.getElementById('modal-kok');
  const perde = h('div', { class: 'perde' });
  const kapat = () => { perde.remove(); document.removeEventListener('keydown', esc); if (kapaninca) kapaninca(); };
  const esc = (e) => { if (e.key === 'Escape') kapat(); };
  document.addEventListener('keydown', esc);
  const alt = h('div', { class: 'modal-alt' }, butonlar.map(b => btn(b.yazi, async () => {
    try { const r = await b.tikla?.(); if (r !== false) kapat(); } catch (e) { /* hata bildirildi */ }
  }, { cls: b.cls, ikon: b.ikon })));
  const m = h('div', { class: 'modal' + (genis ? ' genis' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': baslik },
    h('div', { class: 'modal-ust' }, h('h2', {}, baslik), h('div', { class: 'bosluk' }),
      h('button', { class: 'btn hayalet', onclick: kapat, 'aria-label': 'Kapat', type: 'button' }, ikon('kapat'))),
    h('div', { class: 'modal-govde' }, govde), butonlar.length ? alt : null);
  perde.addEventListener('mousedown', (e) => { if (e.target === perde) kapat(); });
  perde.append(m); kok.append(perde);
  setTimeout(() => (m.querySelector('input, select') || m.querySelector('button.ana') || m).focus?.(), 30);
  return { kapat, el: m };
}
function onayla(baslik, metin, evet = 'Evet', tehlike = false) {
  return new Promise(res => {
    modal({ baslik, govde: metin instanceof Node ? metin : h('p', {}, metin), kapaninca: () => res(false), butonlar: [
      { yazi: 'Vazgeç', tikla: () => res(false) },
      { yazi: evet, cls: tehlike ? 'tehlike' : 'ana', tikla: () => { res(true); } }] });
  });
}
function sor(baslik, etiket, varsayilan = '', o = {}) {
  return new Promise(res => {
    const inp = h('input', { type: o.tur || 'text', value: varsayilan, style: { width: '100%' } });
    const m = modal({ baslik, kapaninca: () => res(null), govde: h('label', { class: 'alan' }, etiket, inp, o.ipucu ? h('span', { class: 'ipucu' }, o.ipucu) : null),
      butonlar: [{ yazi: 'Vazgeç', tikla: () => res(null) }, { yazi: 'Tamam', cls: 'ana', tikla: () => res(inp.value) }] });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { res(inp.value); m.kapat(); } });
  });
}

/* ------------------------------------------------------------------ dosya seçimi */
async function dosyaSec(tur, o = {}) {
  // önce Windows'un kendi penceresi; olmazsa programın gezgini
  try {
    const j = await api('pencere', { tur, baslik: o.baslik || '', baslangic: o.baslangic || S?.varsayilan_klasor || '', uzanti: o.uzanti || '' });
    return j.yollar || [];
  } catch (e) {
    if (e.yanit && e.yanit.yerel_yok) return gezgin(tur, o);
    return [];
  }
}
function gezgin(tur, o = {}) {
  return new Promise(res => {
    let yol = o.baslangic || S?.varsayilan_klasor || '';
    let secili = new Set();
    let veri = null;
    const uzanti = o.uzanti || (tur === 'klasor' || tur === 'dosyalar' ? 'c3d' : '');
    const yolInp = h('input', { type: 'text', value: yol, 'aria-label': 'Klasör yolu' });
    const liste = h('div', { class: 'gezgin-liste' });
    const adInp = h('input', { type: 'text', value: o.dosyaAdi || '', placeholder: 'Dosya adı', style: { flex: 1 } });
    const bilgi = h('div', { class: 'kucuk-yazi', style: { marginTop: '6px' } });
    async function git(y) {
      try { veri = await api('gozat', { yol: y, uzanti }); } catch (e) { return; }
      yol = veri.yol; yolInp.value = yol; secili = new Set(); ciz();
    }
    function ciz() {
      liste.replaceChildren();
      if (veri.ust) liste.append(h('button', { type: 'button', onclick: () => git(veri.ust) }, ikon('ust'), '..'));
      for (const k of veri.klasorler) liste.append(h('button', { type: 'button', ondblclick: () => git(veri.yol + sep() + k),
        onclick: () => git(veri.yol + sep() + k) }, ikon('klasor'), k));
      for (const d of veri.dosyalar) {
        const b = h('button', { type: 'button', class: secili.has(d) ? 'secili' : '', onclick: () => {
          if (tur === 'dosyalar') { secili.has(d) ? secili.delete(d) : secili.add(d); }
          else { secili = new Set([d]); adInp.value = d; }
          ciz();
        }, ondblclick: () => { if (tur === 'ac') { res([veri.yol + sep() + d]); m.kapat(); } } }, ikon('dosya'), d);
        liste.append(b);
      }
      if (!veri.klasorler.length && !veri.dosyalar.length) liste.append(h('div', { class: 'bos' }, 'Bu klasör boş.'));
      bilgi.textContent = tur === 'klasor' ? `Bu klasörde ${veri.dosyalar.length} C3D dosyası var (alt klasörler de taranır).`
        : (tur === 'dosyalar' ? `${secili.size} dosya seçili.` : '');
    }
    const sep = () => (veri && veri.yol.includes('\\')) ? '\\' : '/';
    const suruculer = h('div', { class: 'btn-grup', style: { marginBottom: '8px' } });
    const govde = h('div', {}, suruculer,
      h('div', { class: 'gezgin-yol' }, yolInp, btn('Git', () => git(yolInp.value))), liste, bilgi,
      tur === 'kaydet' ? h('div', { class: 'satir', style: { marginTop: '10px' } }, adInp) : null);
    yolInp.addEventListener('keydown', e => { if (e.key === 'Enter') git(yolInp.value); });
    const etiket = { klasor: 'Bu klasörü seç', dosyalar: 'Seçilenleri ekle', ac: 'Aç', kaydet: 'Kaydet' }[tur];
    const m = modal({ baslik: o.baslik || 'Konum seçin', genis: true, govde, kapaninca: () => res([]), butonlar: [
      { yazi: 'Vazgeç', tikla: () => res([]) },
      { yazi: etiket, cls: 'ana', tikla: () => {
        if (tur === 'klasor') res([veri.yol]);
        else if (tur === 'dosyalar') { if (!secili.size) { bildir('Dosya seçin.'); return false; } res([...secili].map(d => veri.yol + sep() + d)); }
        else if (tur === 'ac') { if (!secili.size) { bildir('Dosya seçin.'); return false; } res([veri.yol + sep() + [...secili][0]]); }
        else { const ad = adInp.value.trim(); if (!ad) { bildir('Dosya adı girin.'); return false; } res([veri.yol + sep() + ad]); }
      } }] });
    git(yol).then(() => {
      for (const d of (veri?.suruculer || [])) suruculer.append(btn(d, () => git(d), { cls: 'kucuk', ikon: 'surucu' }));
      if (veri?.ev) suruculer.append(btn('Ana klasör', () => git(veri.ev), { cls: 'kucuk', ikon: 'ev' }));
    });
  });
}

/* ------------------------------------------------------------------ çizim */
function render() {
  if (!S) return;
  renderUst(); renderYan(); renderIs();
  const kap = document.getElementById('icerik');
  const kaydir = kap.scrollTop;
  // iç tablolardaki kaydırma konumunu da koru (aynı sayfada yeniden çizimde tablo başa dönmesin)
  const icKaydir = UI.sonCizilen === UI.sayfa
    ? [...kap.querySelectorAll('.tablo-kap')].map(e => [e.scrollTop, e.scrollLeft]) : [];
  const odak = document.activeElement && kap.contains(document.activeElement)
    ? document.activeElement.getAttribute('aria-label') : null;
  const sayfa = { dosyalar: sDosyalar, kanallar: sKanallar, sorgular: sSorgular, hastalar: sHastalar, ayarlar: sAyarlar,
    calistir: sCalistir }[UI.sayfa] || sDosyalar;
  koy(kap, h('div', { class: 'sayfa' }, sayfa()));
  kap.querySelectorAll('.tablo-kap').forEach((e, i) => { if (icKaydir[i]) [e.scrollTop, e.scrollLeft] = icKaydir[i]; });
  kap.scrollTop = kaydir;
  if (odak) {
    const el = [...kap.querySelectorAll('[aria-label]')].find(e => e.getAttribute('aria-label') === odak);
    if (el && el.focus) el.focus({ preventScroll: true });
  }
  UI.sonCizilen = UI.sayfa;
}

function renderUst() {
  const p = S.proje;
  koy(document.getElementById('proje-adi'), h('span', {}, 'Proje:'), h('b', { title: p.yol || '' }, p.ad),
    p.degisti ? h('span', { class: 'kaydedilmedi' }, 'kaydedilmedi') : null);
  const ub = document.getElementById('ust-butonlar');
  // dar pencerede yalnızca simge kalır (yazı .etk içinde, CSS gizler); ad title olarak görünür
  const ustBtn = (yazi, tikla, ik) => h('button', { class: 'btn hayalet ust-btn', type: 'button', onclick: tikla, title: yazi },
    ikon(ik), h('span', { class: 'etk' }, yazi));
  ub.replaceChildren(
    ustBtn('Yeni', projeYeni, 'yeni'),
    ustBtn('Aç…', projeAc, 'ac'),
    ustBtn('Kaydet', () => projeKaydet(false), 'kaydet'),
    ustBtn('Farklı kaydet…', () => projeKaydet(true), 'kopya'),
    S.dil === 'en' ? h('button', { class: 'btn hayalet kucuk', type: 'button', onclick: () => dilDegistir('tr'), title: 'Arayüz ve çıktı dili', translate: 'no' }, 'Türkçe')
      : h('button', { class: 'btn hayalet kucuk', type: 'button', onclick: () => dilDegistir('en'), title: 'Interface and output language', translate: 'no' }, 'English'));
}
function yanDarMi() { return UI.yanDar ?? window.innerWidth < 1000; }
let boyutZ = null;
window.addEventListener('resize', () => { clearTimeout(boyutZ); boyutZ = setTimeout(() => { if (S) renderYan(); }, 120); });

function renderIs() {
  const kap = document.getElementById('ust-is');
  const is = S?.is;
  if (!is || !is.calisiyor) { kap.replaceChildren(); return; }
  const oran = is.toplam ? Math.round(100 * is.ilerleme / is.toplam) : 0;
  const ad = is.tur === 'calistir' ? 'Hesaplanıyor' : 'Dosyalar taranıyor';
  koy(kap, h('span', { class: 'kucuk-yazi' }, `${ad} ${is.toplam ? `${is.ilerleme}/${is.toplam}` : ''}`),
    h('div', { class: 'cubuk' + (is.toplam ? '' : ' belirsiz') }, h('i', { style: { width: oran + '%' } })),
    btn('İptal', () => api('iptal'), { cls: 'kucuk' }));
  const ic = document.getElementById('calistir-ilerleme');
  if (ic) koy(ic, ilerlemeCubugu());
}
function ilerlemeCubugu() {
  const is = S.is;
  const oran = is.toplam ? Math.round(100 * is.ilerleme / is.toplam) : 0;
  return h('div', {}, h('div', { class: 'satir', style: { justifyContent: 'space-between', marginBottom: '6px' } },
    h('span', {}, is.mesaj ? `İşleniyor: ${is.mesaj}` : 'Hazırlanıyor…'), h('span', { class: 'kucuk-yazi' }, is.toplam ? `${is.ilerleme} / ${is.toplam}` : '')),
    h('div', { class: 'cubuk' + (is.toplam ? '' : ' belirsiz') }, h('i', { style: { width: oran + '%' } })));
}

function renderYan() {
  const sayfalar = [
    ['dosyalar', 'Dosyalar', S.dosyalar.length ? String(S.dosyalar.length) : ''],
    ['kanallar', 'EMG kanalları', (() => { const n = S.kanallar.filter(k => (k.durum === 'sinyal' || k.durum === 'karisik') && !k.kas && !k.yok_say).length;
      const o = S.kanallar.filter(k => k.oneri).length; return n ? { t: String(n), u: true } : (o ? { t: 'öneri', u: true } : ''); })()],
    ['sorgular', 'Sorgular', S.sorgular.length ? String(S.sorgular.length) : ''],
    ['hastalar', 'Hastalar ve MVIC', S.hastalar.length ? String(S.hastalar.length) : ''],
    ['ayarlar', 'Ayarlar', ''],
    ['calistir', 'Çalıştır ve sonuçlar', S.son_sonuc ? '✓' : ''],
  ];
  const yan = document.getElementById('yan');
  const dar = yanDarMi();
  yan.classList.toggle('dar', dar);
  koy(yan, ...sayfalar.map(([id, ad, r], i) => {
    const rz = typeof r === 'object' ? r : { t: r };
    return h('button', { class: UI.sayfa === id ? 'aktif' : '', type: 'button', title: dar ? ad : null, onclick: () => { UI.sayfa = id; render(); document.getElementById('icerik').scrollTop = 0; } },
      h('span', { class: 'no' }, i + 1), h('span', { class: 'etk' }, ad), rz.t ? h('span', { class: 'rozet' + (rz.u ? ' uyari' : '') }, rz.t) : null);
  }), h('div', { class: 'alt' }, h('span', { class: 'etk', translate: 'no' }, `${S.program.ad} ${S.program.surum}`),
    h('button', { class: 'btn hayalet', type: 'button', title: dar ? 'Menüyü genişlet' : 'Menüyü daralt', 'aria-label': dar ? 'Menüyü genişlet' : 'Menüyü daralt',
      onclick: () => { UI.yanDar = !dar; renderYan(); } }, ikon(dar ? 'genislet' : 'daralt'))));
}

function baslik(metin, aciklama, ...sag) {
  return [h('div', { class: 'sayfa-baslik' }, h('h1', {}, metin), h('div', { class: 'bosluk' }), ...sag),
    aciklama ? h('p', { class: 'sayfa-aciklama' }, aciklama) : null];
}

/* ================================================================== 1. DOSYALAR */
function sDosyalar() {
  const d = S.dosyalar;
  const ekle = async (tur) => {
    const yollar = await dosyaSec(tur, { baslik: tur === 'klasor' ? 'C3D klasörü seçin' : 'C3D dosyaları seçin' });
    if (yollar.length) islem('dosya_ekle', { yollar });
  };
  const ustB = [btn('Klasör ekle…', () => ekle('klasor'), { cls: 'ana', ikon: 'klasor' }), btn('Dosya ekle…', () => ekle('dosyalar'), { ikon: 'dosya' })];
  if (!d.length) {
    return [...baslik('C3D dosyaları', 'Analiz edilecek C3D dosyalarını ekleyin. Program her dosyadan hasta adını, ölçüm tarihini, döngüleri ve EMG kanallarını okur.'),
      h('div', { class: 'kart bos' }, ikon('klasor', 'buyuk-ikon'), h('h3', {}, 'Henüz dosya yok'),
        h('p', {}, 'Bir klasör seçerseniz alt klasörlerdeki tüm C3D dosyaları eklenir.'), h('div', { class: 'btn-grup' }, ...ustB))];
  }
  const hastaSay = new Set(d.map(x => x.hasta + '|' + x.tarih)).size;
  const tarihsiz = d.filter(x => !x.tarih).length;
  const filtre = UI.dosyaFiltre.toLocaleLowerCase('tr');
  const gorunen = d.filter(x => !filtre || (x.dosya + ' ' + x.hasta + ' ' + x.tarih).toLocaleLowerCase('tr').includes(filtre));
  const secili = [...UI.secili].filter(y => d.some(x => x.yol === y));
  const dahilSay = gorunen.filter(x => x.dahil).length;
  const tumu = gorunen.length && dahilSay === gorunen.length;
  const satirSec = (x, e) => {
    if (e.target.closest('input, button, select, a, label')) return;
    if (e.shiftKey && UI.sonSecili) {
      const i = gorunen.findIndex(g => g.yol === UI.sonSecili), j = gorunen.findIndex(g => g.yol === x.yol);
      if (i >= 0 && j >= 0) { if (!(e.ctrlKey || e.metaKey)) UI.secili.clear(); for (let k = Math.min(i, j); k <= Math.max(i, j); k++) UI.secili.add(gorunen[k].yol); }
    } else if (e.ctrlKey || e.metaKey) {
      UI.secili.has(x.yol) ? UI.secili.delete(x.yol) : UI.secili.add(x.yol); UI.sonSecili = x.yol;
    } else {
      const tek = UI.secili.size === 1 && UI.secili.has(x.yol);
      UI.secili.clear(); if (!tek) UI.secili.add(x.yol); UI.sonSecili = x.yol;
    }
    render();
  };
  const kutular = [];
  if (S.benzer_adlar.length) kutular.push(h('div', { class: 'kutu uyari' }, ikon('uyari'), h('div', { class: 'govde-m' },
    h('b', {}, 'Yazımı benzeyen hasta adları var. '), 'Aynı kişiyse adları eşitleyin, yoksa ortalamalar ikiye bölünür: ',
    S.benzer_adlar.map(g => g.join(' / ')).join('; '))));
  if (tarihsiz) kutular.push(h('div', { class: 'kutu uyari' }, ikon('uyari'), h('div', { class: 'govde-m' },
    h('b', {}, `${tarihsiz} dosyada ölçüm tarihi yok. `), 'Program tarihi C3D\'nin içinden ya da dosyanın bulunduğu klasörün adından okur (ör. …\\Hasta Adı\\13 01 2026\\). ',
    'Bu dosyaların klasör adında tarih yok. Tarihi tabloda girin ya da satırlara tıklayarak seçip "Tarih ata…" kullanın.')));
  const toplu = secili.length ? h('div', { class: 'btn-grup' }, h('span', { class: 'kucuk-yazi' }, `${secili.length} seçili:`),
    btn('Hasta adı ata…', async () => { const v = await sor('Hasta adı', 'Seçili dosyaların hasta adı', d.find(x => x.yol === secili[0])?.hasta || ''); if (v) islem('dosya_guncelle', { yollar: secili, hasta: v }); }, { cls: 'kucuk' }),
    btn('Tarih ata…', async () => { const v = await sor('Ölçüm tarihi', 'Seçili dosyaların ölçüm tarihi', d.find(x => x.yol === secili[0])?.tarih || '', { tur: 'date' }); if (v !== null) islem('dosya_guncelle', { yollar: secili, tarih: v }); }, { cls: 'kucuk' }),
    btn('Listeden çıkar', async () => { if (await onayla('Dosyaları çıkar', `${secili.length} dosya listeden çıkarılsın mı? (Diskteki dosyalar silinmez.)`, 'Çıkar', true)) { UI.secili.clear(); islem('dosya_cikar', { yollar: secili }); } }, { cls: 'kucuk tehlike', ikon: 'cop' }),
    btn('Seçimi kaldır', () => { UI.secili.clear(); render(); }, { cls: 'kucuk hayalet' }))
    : h('span', { class: 'kucuk-yazi' }, 'Tik = hesaplamaya dahil. Toplu işlem için satırlara tıklayın (Ctrl ya da Shift ile birden fazla).');

  const satirlar = gorunen.map(x => {
    let kaynakIkon;
    if (!x.tarih) kaynakIkon = h('span', { class: 'etiket uyari' }, 'yok');
    else if (/elle/.test(x.tarih_kaynagi)) kaynakIkon = h('span', { class: 'etiket', title: 'Elle girildi' }, 'elle');
    else kaynakIkon = h('span', { class: 'etiket ok', title: x.tarih_kaynagi || '' }, '✓');
    let durum;
    if (x.durum === 'tamam') durum = h('span', { class: 'etiket ok' }, 'hazır');
    else if (x.durum === 'degisti') durum = h('span', { class: 'etiket uyari', title: 'Dosya eklendikten sonra değişmiş (Nexus\'ta yeniden işlenmiş olabilir). Çalıştırmada güncel hali kullanılır.' }, 'değişti');
    else if (x.durum === 'hata') durum = h('span', { class: 'etiket hata', title: x.hata }, 'okunamadı');
    else durum = h('span', { class: 'etiket' }, 'taranıyor');
    return h('tr', { class: (UI.secili.has(x.yol) ? 'secili ' : '') + (x.dahil ? '' : 'soluk'), onclick: (e) => satirSec(x, e),
      onmousedown: (e) => { if (e.shiftKey && !e.target.closest('input, select')) e.preventDefault(); } },
      h('td', {}, h('input', { type: 'checkbox', checked: x.dahil, 'aria-label': 'Dahil ' + x.dosya, title: 'Hesaplamaya dahil',
        onchange: (e) => islem('dosya_guncelle', { yol: x.yol, dahil: e.target.checked }) })),
      h('td', { style: { maxWidth: '300px' } }, h('div', { class: 'tasma', title: x.dosya }, x.dosya), h('div', { class: 'yol', title: x.klasor }, x.klasor)),
      h('td', {}, h('input', { type: 'text', value: x.hasta, 'aria-label': 'Hasta adı', style: { minWidth: '150px' }, onchange: (e) => islem('dosya_guncelle', { yol: x.yol, hasta: e.target.value }) }),
        x.subject && x.subject !== x.hasta ? h('div', { class: 'kucuk-yazi', title: 'C3D içindeki denek adı' }, 'C3D: ' + x.subject) : null),
      h('td', {}, h('div', { class: 'tarih-hucre' },
        h('input', { type: 'date', value: x.tarih, 'aria-label': 'Ölçüm tarihi', onchange: (e) => islem('dosya_guncelle', { yol: x.yol, tarih: e.target.value }) }), kaynakIkon)),
      h('td', { class: 'sayi' }, x.dongu_L ?? '–', ' / ', x.dongu_R ?? '–'),
      h('td', { class: 'sayi' }, x.kinetik_L ?? '–', ' / ', x.kinetik_R ?? '–'),
      h('td', { class: 'sayi' }, x.emg_kanal ? `${x.emg_eslesen}/${x.emg_kanal}` : '–'),
      h('td', { class: 'sayi' }, x.uyari_sayisi ? h('button', { class: 'btn kucuk', type: 'button', onclick: () => dosyaUyarilari(x) }, ikon('uyari'), x.uyari_sayisi)
        : (x.uyarilar?.length ? h('button', { class: 'btn hayalet kucuk', type: 'button', onclick: () => dosyaUyarilari(x) }, 'bilgi') : '–')),
      h('td', {}, durum, x.dahil ? null : h('span', { class: 'etiket', style: { marginLeft: '4px' } }, 'hariç')));
  });
  return [...baslik('C3D dosyaları', 'Hasta adı dosya adından, ölçüm tarihi klasör adından (ör. 13 01 2026) okunur. İkisini de tabloda düzeltebilirsiniz; ortalamalar hasta + tarih bazında alınır.',
    ...ustB, btn('Yeniden tara', () => islem('yeniden_tara'), { ikon: 'yenile', cls: 'hayalet' })),
  ...kutular,
  h('div', { class: 'ozetler' },
    ozet(d.length, 'dosya'), ozet(hastaSay, 'hasta + tarih'), ozet(d.reduce((a, x) => a + (x.dongu_L || 0) + (x.dongu_R || 0), 0), 'döngü'),
    ozet(d.reduce((a, x) => a + (x.kinetik_L || 0) + (x.kinetik_R || 0), 0), 'kinetik döngü'),
    ozet(d.filter(x => !x.dahil).length, 'hariç dosya')),
  h('div', { class: 'kart' },
    h('div', { class: 'kart-ust' }, h('input', { type: 'search', placeholder: 'Ara: dosya, hasta, tarih', value: UI.dosyaFiltre, style: { width: '280px' },
      oninput: (e) => { UI.dosyaFiltre = e.target.value; const pos = e.target.selectionStart; render(); const i = document.querySelector('input[type=search]'); if (i) { i.focus(); i.setSelectionRange(pos, pos); } } }),
    h('div', { class: 'bosluk' }), toplu),
    h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo secilebilir' },
      h('thead', {}, h('tr', {}, h('th', { title: 'Tik = hesaplamaya dahil. Başlıktaki kutu listede görünen tüm dosyaları açar ya da kapatır.' }, (() => {
        const kutu = h('input', { type: 'checkbox', checked: tumu, 'aria-label': 'Görünenlerin tümünü dahil et',
          onchange: (e) => islem('dosya_guncelle', { yollar: gorunen.map(x => x.yol), dahil: e.target.checked }) });
        kutu.indeterminate = dahilSay > 0 && dahilSay < gorunen.length;
        return kutu; })()),
        h('th', {}, 'Dosya'), h('th', {}, 'Hasta'), h('th', {}, 'Ölçüm tarihi'), h('th', { class: 'sayi', title: 'Geçerli döngü sayısı' }, 'Döngü S/Sğ'),
        h('th', { class: 'sayi', title: 'Kuvvet plakasına basılan döngüler' }, 'Kinetik S/Sğ'), h('th', { class: 'sayi', title: 'Eşleştirilen / toplam EMG kanalı' }, 'EMG'),
        h('th', { class: 'sayi' }, 'Uyarı'), h('th', {}, 'Durum'))),
      h('tbody', {}, satirlar))))];
}
function ozet(d, e, cls = '') { return h('div', { class: 'ozet ' + cls }, h('div', { class: 'd' }, d), h('div', { class: 'e' }, e)); }
function dosyaUyarilari(x) {
  modal({ baslik: x.dosya, genis: true, govde: h('div', {},
    h('p', { class: 'kucuk-yazi' }, 'Dosya taramasında görülenler. Program event\'leri ya da veriyi düzeltmez; düzeltme Nexus\'ta yapılır.'),
    h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, h('th', {}, 'Önem'), h('th', {}, 'Konu'), h('th', {}, 'Açıklama'))),
      h('tbody', {}, (x.uyarilar || []).map(u => h('tr', {}, h('td', {}, onemEtiket(u.onem)), h('td', {}, u.kategori), h('td', {}, u.mesaj))))))),
  butonlar: [{ yazi: 'Kapat', cls: 'ana' }] });
}
function onemEtiket(o) { return h('span', { class: 'etiket ' + ({ Hata: 'hata', 'Uyarı': 'uyari', Bilgi: 'bilgi' }[o] || '') }, o); }

/* ================================================================== 2. EMG KANALLARI */
function sKanallar() {
  const k = S.kanallar;
  const kaslar = S.katalog.kaslar;
  if (!k.length) return [...baslik('EMG kanalları'), h('div', { class: 'kart bos' }, h('h3', {}, 'EMG kanalı yok'),
    h('p', {}, S.dosyalar.length ? 'Yüklenen dosyalarda EMG kanalı bulunamadı.' : 'Önce "Dosyalar" adımında C3D ekleyin.'))];
  const oneriVar = k.some(x => x.oneri);
  const eslesme = {};
  for (const x of k) if (x.kas) (eslesme[x.kas] = eslesme[x.kas] || {})[x.taraf] = (eslesme[x.kas][x.taraf] || []).concat(x.ad);
  const kasSecenek = [{ v: '', t: '— kullanma —' }, ...kaslar.map(m => ({ v: m.kod, t: `${m.kod} – ${m.ad}` })), { v: '__yeni__', t: '+ Yeni kas ekle…' }];
  const satirlar = k.map(x => {
    const dur = { sinyal: h('span', { class: 'etiket ok' }, h('span', { class: 'nokta' }), 'kas sinyali'),
      karisik: h('span', { class: 'etiket uyari', title: x.aciklama }, h('span', { class: 'nokta' }), 'kısmen'),
      parazit: h('span', { class: 'etiket', title: x.aciklama }, h('span', { class: 'nokta' }), 'yalnızca 50 Hz parazit'),
      bos: h('span', { class: 'etiket' }, 'boş') }[x.durum];
    return h('tr', { class: x.durum === 'parazit' || x.durum === 'bos' ? 'soluk' : '' },
      h('td', { class: 'kod' }, x.ad), h('td', { class: 'sayi' }, x.dosya_sayisi), h('td', {}, dur),
      h('td', { class: 'sayi' }, x.rms != null ? fmt(x.rms, 0) : ''),
      h('td', {}, sec(kasSecenek, x.kas, async (v) => {
        if (v === '__yeni__') { await yeniKas(); return; }
        islem('kanal_esle', { ad: x.ad, kas: v, taraf: x.taraf || x.oneri_taraf });
      }, { aria: 'Kas ' + x.ad, style: { minWidth: '230px' } })),
      h('td', {}, sec([{ v: '', t: '—' }, { v: 'L', t: 'Sol' }, { v: 'R', t: 'Sağ' }], x.taraf, (v) => islem('kanal_esle', { ad: x.ad, kas: x.kas, taraf: v }),
        { disabled: !x.kas, aria: 'Taraf ' + x.ad })),
      h('td', {}, x.oneri ? h('span', { class: 'etiket bilgi', title: 'Kanal adından önerildi' }, 'öneri') : (x.kas ? h('span', { class: 'etiket ok' }, 'eşleşti') : '')));
  });
  const ozetSat = Object.keys(eslesme).sort().map(kas => h('span', { class: 'etiket vurgu', style: { marginRight: '6px' } },
    `${kas}: ${['L', 'R'].filter(t => eslesme[kas][t]).map(t => TARAF[t]).join(' + ') || '?'}`));
  return [...baslik('EMG kanalları', 'Her EMG kanalını bir kasa ve tarafa eşleştirin. Aynı kas farklı dosyalarda farklı adla kaydedildiyse her adı aynı kasa eşleştirin. Program eşleştirmeleri hatırlar; sonraki projelerde aynı kanal adı otomatik eşleşir. Kuvvet plakası, senkron ve ayak anahtarı kanalları listede yok.'),
    oneriVar ? h('div', { class: 'kutu bilgi' }, ikon('bilgi'), h('div', { class: 'govde-m' }, 'Bazı kanallar adlarından eşleştirildi ("öneri"). Kontrol edin, doğruysa onaylayın.'),
      btn('Önerileri onayla', () => islem('kanal_onerilerini_onayla'), { cls: 'ana kucuk', ikon: 'tamam' })) : null,
    h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, 'Eşleşen kaslar'), h('div', {}, ozetSat.length ? ozetSat : h('span', { class: 'kucuk-yazi' }, 'Henüz yok.')),
      h('div', { class: 'bosluk' }), btn('Yeni kas…', yeniKas, { ikon: 'arti', cls: 'kucuk' })),
      h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, h('th', {}, 'Kanal adı (C3D)'), h('th', { class: 'sayi' }, 'Dosya'),
        h('th', {}, 'Sinyal'), h('th', { class: 'sayi', title: '20–450 Hz bant geçiren sonrası RMS, dosyaların medyanı' }, 'RMS µV'), h('th', {}, 'Kas'), h('th', {}, 'Taraf'), h('th', {}, ''))),
        h('tbody', {}, satirlar))))];
}
async function yeniKas() {
  const kod = h('input', { type: 'text', placeholder: 'ör. ADDM', style: { width: '140px' } });
  const ad = h('input', { type: 'text', placeholder: 'ör. Adductor magnus', style: { width: '100%' } });
  modal({ baslik: 'Yeni kas', govde: h('div', { class: 'satir' }, h('label', { class: 'alan' }, 'Kısa kod', kod), h('label', { class: 'alan', style: { flex: 1 } }, 'Kas adı', ad)),
    butonlar: [{ yazi: 'Vazgeç' }, { yazi: 'Ekle', cls: 'ana', tikla: () => islem('kas_ekle', { kod: kod.value, ad: ad.value }) }] });
}

/* ================================================================== 3. SORGULAR */
function katalogDegisken(id) {
  for (const g of S.katalog.gruplar) for (const d of g.degiskenler) if (d.id === id) return { ...d, grup: g.id };
  return null;
}
function aralikBul(id) { return S.katalog.araliklar.find(a => a.id === id); }
function varsayilanB() {
  return { aralik: 'ST', grup: 'kinematik', degisken: 'KneeAngles', bilesen: 'X', taraf: 'ipsi', ist: 'max', zb: '%GC', par: {},
    kod: '', kodElle: false, aciklama: '', indeks: null };
}
function istSecenekleri(b) {
  const d = katalogDegisken(b.degisken);
  if (!d) return [];
  if (d.tur === 'faz') return S.katalog.faz_istatistikleri.map(i => ({ v: i.id, t: i.ad, tur: i.tur }));
  if (d.tur === 'zu') return [{ v: 'deger', t: 'Değer', tur: 'an' }];
  const a = aralikBul(b.aralik);
  if (a && a.an) return [{ v: 'deger', t: 'Değer (seçilen andaki)', tur: 'an' }];
  return S.katalog.istatistikler.filter(i => i.id !== 'deger' && (d.tur === 'emg' || !['emg', 'emg_zaman', 'emg_trial', 'cci'].includes(i.tur)))
    .map(i => ({ v: i.id, t: i.ad, tur: i.tur, aciklama: i.aciklama }));
}
function bDuzelt(b) {
  const d = katalogDegisken(b.degisken);
  if (!d) {
    const g = S.katalog.gruplar.find(x => x.id === b.grup) || S.katalog.gruplar[0];
    b.degisken = (g.degiskenler.find(x => x.var) || g.degiskenler[0] || {}).id || '';
  }
  const dd = katalogDegisken(b.degisken);
  if (dd) {
    const bl = dd.bilesenler || [];
    if (bl.length && !bl.some(x => x.kod === b.bilesen)) b.bilesen = bl[0].kod;
    if (!bl.length) b.bilesen = dd.tur === 'emg' ? 'E' : null;
    if (['kinetik', 'grf', 'faz', 'zu'].includes(dd.tur)) b.taraf = 'ipsi';
  }
  const ist = istSecenekleri(b);
  if (ist.length && !ist.some(x => x.v === b.ist)) b.ist = ist[0].v;
  return b;
}
let kodZamanlayici = null;
function kodGuncelle() {
  if (UI.b.kodElle) return;
  clearTimeout(kodZamanlayici);
  kodZamanlayici = setTimeout(async () => {
    try { const j = await api('kod_oner', { sorgu: bSorgu() }); if (!UI.b.kodElle) { UI.b.kod = j.kod; const i = document.getElementById('kod-girdi'); if (i) i.value = j.kod; } } catch (e) {}
  }, 120);
}
function bSorgu() {
  const b = UI.b;
  const d = katalogDegisken(b.degisken);
  const par = {};
  for (const [k, v] of Object.entries(b.par || {})) if (v !== '' && v !== null && v !== undefined) par[k] = isNaN(Number(v)) || k === 'kas2' || k === 'taraf2' ? v : Number(v);
  return { kod: b.kodElle ? b.kod : '', degisken: b.degisken, bilesen: b.bilesen, aralik: d && ['zu', 'faz'].includes(d.tur) ? null : b.aralik,
    ist: b.ist, zaman_birimi: b.zb, taraf: b.taraf, par, aciklama: b.aciklama };
}

function sSorgular() {
  if (!UI.b) UI.b = varsayilanB();
  const b = bDuzelt(UI.b);
  const d = katalogDegisken(b.degisken);
  const aralikGerekmez = d && ['zu', 'faz'].includes(d.tur);
  const yenile = () => { bDuzelt(UI.b); kodGuncelle(); render(); };

  // 1. aralık
  const gruplar = {};
  for (const a of S.katalog.araliklar) (gruplar[a.grup] = gruplar[a.grup] || []).push(a);
  const aralikSec = sec(['Aralıklar', 'Anlar', 'Özel aralıklar', 'Referans anlar', 'Güç fazı tepe anları'].filter(g => gruplar[g])
    .map(g => ({ grup: g, secenekler: gruplar[g].map(a => ({ v: a.id, t: a.ad })) })), b.aralik, v => { UI.b.aralik = v; yenile(); },
  { disabled: aralikGerekmez, aria: 'Aralık ya da an' });
  const aSecili = aralikBul(b.aralik);
  const adim1 = h('div', { class: 'adim' + (aralikGerekmez ? ' pasif' : '') },
    h('div', { class: 'adim-baslik' }, h('span', { class: 'no' }, '1'), 'Aralık ya da an'), aralikSec,
    h('div', { class: 'not' }, aralikGerekmez ? 'Bu değişken için aralık gerekmez.' : (aSecili ? aSecili.ozet : '')),
    h('div', { class: 'btn-grup' }, btn('Özel aralık…', () => ozelAralikModal(), { cls: 'kucuk', ikon: 'arti' }),
      btn('Referans an…', () => refModal(), { cls: 'kucuk', ikon: 'arti' })));

  // 2. değişken
  const grupSeg = h('div', { class: 'segment', role: 'tablist' }, S.katalog.gruplar.filter(g => g.degiskenler.length || g.id !== 'emg').map(g =>
    h('button', { type: 'button', class: b.grup === g.id ? 'aktif' : '', onclick: () => { UI.b.grup = g.id; UI.b.degisken = (g.degiskenler.find(x => x.var) || g.degiskenler[0] || {}).id || ''; yenile(); } }, g.ad)));
  const grup = S.katalog.gruplar.find(g => g.id === b.grup) || S.katalog.gruplar[0];
  const degSec = grup.degiskenler.length ? sec(grup.degiskenler.map(x => ({ v: x.id, t: x.ad + (x.var ? '' : ' (dosyalarda yok)') })), b.degisken,
    v => { UI.b.degisken = v; yenile(); }, { aria: 'Değişken' }) : h('div', { class: 'not' }, b.grup === 'emg' ? 'Önce "EMG kanalları" sayfasında kanalları kaslara eşleştirin.' : 'Değişken yok.');
  const bl = d?.bilesenler || [];
  const bilSec = bl.length > 1 ? sec(bl.map(x => ({ v: x.kod, t: `${x.ad} (${x.kod})${x.isaret ? ' – ' + x.isaret : ''}` })), b.bilesen, v => { UI.b.bilesen = v; yenile(); }, { aria: 'Bileşen' }) : null;
  const tarafSec = d && ['kinematik', 'emg', 'turetilmis'].includes(d.tur) ? sec([{ v: 'ipsi', t: 'Döngünün tarafı (aynı taraf)' }, { v: 'karsi', t: 'Karşı taraf' }], b.taraf,
    v => { UI.b.taraf = v; yenile(); }, { aria: 'Taraf' }) : null;
  const adim2 = h('div', { class: 'adim' }, h('div', { class: 'adim-baslik' }, h('span', { class: 'no' }, '2'), 'Değişken'), grupSeg, degSec,
    bilSec ? h('label', { class: 'alan' }, 'Bileşen / düzlem', bilSec) : null,
    tarafSec ? h('label', { class: 'alan' }, 'Taraf', tarafSec) : null,
    d && d.aciklama ? h('div', { class: 'not' }, d.aciklama) : null);

  // 3. istatistik
  const istler = istSecenekleri(b);
  const ist = istler.find(i => i.v === b.ist) || {};
  const istSec = sec(istler, b.ist, v => { UI.b.ist = v; yenile(); }, { aria: 'İstatistik', disabled: istler.length <= 1 });
  const zamanTur = ['zaman', 'emg_zaman'].includes(ist.tur);
  const sureTur = ist.tur === 'sure';
  const zb = zamanTur ? sec(Object.entries(S.katalog.zaman_birimleri).map(([v, t]) => ({ v, t })), b.zb, v => { UI.b.zb = v; yenile(); }, { aria: 'Zaman birimi' })
    : (sureTur ? sec(Object.entries(S.katalog.sure_birimleri).map(([v, t]) => ({ v, t })), b.zb in S.katalog.sure_birimleri ? b.zb : 's', v => { UI.b.zb = v; yenile(); }, { aria: 'Süre birimi' }) : null);
  if (sureTur && !(b.zb in S.katalog.sure_birimleri)) UI.b.zb = 's';
  const ekler = [];
  if (['tmax', 'tmin'].includes(b.ist)) ekler.push(h('label', { class: 'alan' }, 'Tepe zamanı için yumuşatma (ms)', h('input', { type: 'number', min: 0, step: 10, value: b.par.yumusatma_ms ?? '',
    placeholder: '0', onchange: e => { UI.b.par.yumusatma_ms = e.target.value; kodGuncelle(); } }), h('span', { class: 'ipucu' }, 'Boş = yok. Gürültülü sinyalde tepe zamanı sıçramasın diye.')));
  if (b.ist === 'tepe2') ekler.push(h('label', { class: 'alan' }, 'En az vadi derinliği', h('input', { type: 'number', min: 0, step: 0.05, value: b.par.vadi_esik ?? '',
    placeholder: 'otomatik', onchange: e => { UI.b.par.vadi_esik = e.target.value; } }), h('span', { class: 'ipucu' }, 'Değişkenin biriminde. Boş = tepe değerinin %3\'ü.')));
  if (b.ist === 'cci') {
    const kaslar = S.katalog.kaslar.filter(k => k.eslesmis && 'EMG:' + k.kod !== b.degisken);
    ekler.push(h('label', { class: 'alan' }, 'İkinci kas', sec([{ v: '', t: '— seçin —' }, ...kaslar.map(k => ({ v: k.kod, t: `${k.kod} – ${k.ad}` }))], b.par.kas2 || '', v => { UI.b.par.kas2 = v; yenile(); })));
    ekler.push(h('label', { class: 'alan' }, 'İkinci kasın tarafı', sec([{ v: 'ayni', t: 'Aynı taraf' }, { v: 'karsi', t: 'Karşı taraf' }], b.par.taraf2 || 'ayni', v => { UI.b.par.taraf2 = v; })));
  }
  const adim3 = h('div', { class: 'adim' }, h('div', { class: 'adim-baslik' }, h('span', { class: 'no' }, '3'), 'İstatistik'), istSec,
    ist.aciklama ? h('div', { class: 'not' }, ist.aciklama) : null,
    zb ? h('label', { class: 'alan' }, zamanTur ? 'Zaman birimi' : 'Süre birimi', zb) : null, ...ekler);

  const kodInp = h('input', { type: 'text', id: 'kod-girdi', value: b.kod, placeholder: 'otomatik', 'aria-label': 'Sütun adı',
    oninput: e => { UI.b.kod = e.target.value; UI.b.kodElle = !!e.target.value; } });
  const acikInp = h('input', { type: 'text', value: b.aciklama, placeholder: 'İsteğe bağlı (değişken sözlüğüne yazılır)', oninput: e => { UI.b.aciklama = e.target.value; } });
  const ekleBtn = btn(b.indeks !== null ? 'Güncelle' : 'Listeye ekle', async () => {
    try { await islem('sorgu_ekle', { sorgu: bSorgu(), indeks: b.indeks }); UI.b.kodElle = false; UI.b.kod = ''; UI.b.aciklama = ''; UI.b.indeks = null; kodGuncelle(); render(); } catch (e) {}
  }, { cls: 'ana', ikon: b.indeks !== null ? 'tamam' : 'arti' });
  if (!b.kod) kodGuncelle();

  const olusturucu = h('div', { class: 'kart' },
    h('div', { class: 'kart-ust' }, h('h2', {}, b.indeks !== null ? `Sorguyu düzenle (#${b.indeks + 1})` : 'Yeni sorgu'), h('div', { class: 'bosluk' }),
      b.indeks !== null ? btn('Düzenlemeyi bırak', () => { UI.b = varsayilanB(); render(); }, { cls: 'hayalet kucuk' }) : null),
    h('div', { class: 'olusturucu' }, adim1, adim2, adim3),
    h('div', { class: 'olusturucu-alt' }, h('label', { class: 'alan kod-alan' }, 'Excel sütun adı', kodInp),
      h('label', { class: 'alan acik-alan' }, 'Açıklama', acikInp), ekleBtn),
    h('p', { class: 'kucuk-yazi', style: { margin: '6px 0 0' } }, 'Sütun adı boş bırakılırsa otomatik verilir. Taraf bazlı değişkenler Excel\'de "L_" ve "R_" önekleriyle iki sütun olur.'));

  // paketler ve şablonlar
  const paketler = h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, 'Hazır paketler ve şablonlar'), h('div', { class: 'bosluk' }),
    btn('Şablon yükle…', async () => { const y = await dosyaSec('ac', { uzanti: 'json', baslik: 'Sorgu şablonu açın' }); if (y.length) islem('sablon_yukle', { yol: y[0] }); }, { ikon: 'ac', cls: 'kucuk' }),
    btn('Şablon olarak kaydet…', async () => { const y = await dosyaSec('kaydet', { uzanti: 'json', baslik: 'Sorgu şablonunu kaydedin', dosyaAdi: 'sorgu_sablonu.json' }); if (y.length) islem('sablon_kaydet', { yol: y[0] }); }, { ikon: 'kaydet', cls: 'kucuk', disabled: !S.sorgular.length })),
    h('div', { class: 'paketler' }, h('span', { class: 'kucuk-yazi' }, 'Örnek çalışma paketleri:'),
      S.katalog.paketler.map(p => btn(h('span', {}, h('b', {}, p.id), ' ', p.ad.split(' – ').slice(1).join(' – ') || p.ad, h('span', { class: 'kucuk-yazi' }, ` · ${p.n} sorgu`)),
        () => islem('paket_ekle', { paket: p.id }), { cls: 'kucuk', title: p.ad, aria: 'Paket ' + p.id }))),
    h('p', { class: 'kucuk-yazi', style: { margin: '8px 0 0' } }, 'Şablon; sorguları, özel aralıkları ve referans anları içerir. Meslektaşlarınızla paylaşabilirsiniz.'));

  // liste
  const satirlar = S.sorgular.map((q, i) => h('tr', { class: b.indeks === i ? 'secili' : '' },
    h('td', { class: 'sayi kucuk-yazi' }, i + 1),
    h('td', { class: 'kod' }, h('input', { type: 'text', value: q.kod, style: { fontFamily: 'var(--mono)', minWidth: '230px' }, 'aria-label': 'Sütun adı',
      onchange: e => islem('sorgu_kod', { indeks: i, kod: e.target.value }) })),
    h('td', {}, q.ozet.aralik), h('td', {}, q.ozet.degisken, q.ozet.bilesen ? h('div', { class: 'kucuk-yazi' }, q.ozet.bilesen) : null, q.ozet.taraf ? h('div', { class: 'kucuk-yazi' }, q.ozet.taraf) : null),
    h('td', {}, q.ozet.ist), h('td', {}, q.ozet.birim), h('td', {}, q.paket ? h('span', { class: 'etiket vurgu' }, q.paket) : ''),
    h('td', { class: 'islem' },
      h('button', { class: 'btn hayalet', type: 'button', title: 'Yukarı', 'aria-label': 'Yukarı', onclick: () => islem('sorgu_tasi', { indeks: i, yon: -1 }), disabled: i === 0 }, ikon('yukari')),
      h('button', { class: 'btn hayalet', type: 'button', title: 'Aşağı', 'aria-label': 'Aşağı', onclick: () => islem('sorgu_tasi', { indeks: i, yon: 1 }), disabled: i === S.sorgular.length - 1 }, ikon('asagi')),
      h('button', { class: 'btn hayalet', type: 'button', title: 'Düzenle', 'aria-label': 'Düzenle', onclick: () => sorguDuzenle(q, i) }, ikon('kalem')),
      h('button', { class: 'btn hayalet tehlike', type: 'button', title: 'Sil', 'aria-label': 'Sil', onclick: () => islem('sorgu_sil', { indeksler: [i] }) }, ikon('cop')))));
  const liste = h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, `Sorgu listesi (${S.sorgular.length})`), h('div', { class: 'bosluk' }),
    S.sorgular.length ? btn('Tümünü sil', async () => { if (await onayla('Sorguları sil', 'Listedeki tüm sorgular silinsin mi?', 'Sil', true)) islem('sorgulari_temizle'); }, { cls: 'kucuk tehlike' }) : null),
    S.sorgular.length ? h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, h('th', {}, '#'), h('th', {}, 'Excel sütun adı'),
      h('th', {}, 'Aralık / an'), h('th', {}, 'Değişken'), h('th', {}, 'İstatistik'), h('th', {}, 'Birim'), h('th', {}, 'Paket'), h('th', {}, ''))), h('tbody', {}, satirlar)))
      : h('p', { class: 'kucuk-yazi' }, 'Henüz sorgu yok. Yukarıdan ekleyin ya da hazır bir paket seçin.'));

  // özel aralıklar & referans anlar
  const ozel = h('div', { class: 'iki-sutun' },
    h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, `Özel aralıklar (${S.ozel_araliklar.length})`), h('div', { class: 'bosluk' }), btn('Yeni…', () => ozelAralikModal(), { cls: 'kucuk', ikon: 'arti' })),
      S.ozel_araliklar.length ? h('table', { class: 'tablo' }, h('tbody', {}, S.ozel_araliklar.map(a => h('tr', {}, h('td', {}, h('b', {}, a.ad), h('div', { class: 'kucuk-yazi' }, a.ozet)),
        h('td', { class: 'islem' },
          h('button', { class: 'btn hayalet', type: 'button', title: 'Düzenle', 'aria-label': 'Düzenle ' + a.ad, onclick: () => ozelAralikModal(a) }, ikon('kalem')),
          h('button', { class: 'btn hayalet tehlike', type: 'button', title: 'Sil', 'aria-label': 'Sil ' + a.ad, onclick: () => silOnayli('aralik', a) }, ikon('cop')))))))
        : h('p', { class: 'kucuk-yazi' }, 'Örn. %GC 0–2, %48–52, IC öncesi 100 ms ya da IC → referans an.')),
    h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, `Referans anlar (${S.refler.length})`), h('div', { class: 'bosluk' }), btn('Yeni…', () => refModal(), { cls: 'kucuk', ikon: 'arti' })),
      S.refler.length ? h('table', { class: 'tablo' }, h('tbody', {}, S.refler.map(r => h('tr', {}, h('td', {}, h('b', {}, r.ad), h('div', { class: 'kucuk-yazi' }, r.ozet)),
        h('td', { class: 'islem' },
          h('button', { class: 'btn hayalet', type: 'button', title: 'Düzenle', 'aria-label': 'Düzenle ' + r.ad, onclick: () => refModal(r) }, ikon('kalem')),
          h('button', { class: 'btn hayalet tehlike', type: 'button', title: 'Sil', 'aria-label': 'Sil ' + r.ad, onclick: () => silOnayli('ref', r) }, ikon('cop')))))))
        : h('p', { class: 'kucuk-yazi' }, 'Örn. "pik ayak bileği gücü anı", "pik diz fleksör momenti anı". Winter güç fazlarının tepe anları hazır gelir.')));

  return [...baslik('Sorgular', 'Her sorgu Excel\'de bir değişken olur: önce aralığı ya da anı, sonra o aralıktaki değişkeni, sonra istatistiği seçin.'),
    olusturucu, paketler, liste, ozel, dalgaKarti()];
}

function dalgaKarti() {
  if (!UI.w) UI.w = { grup: 'kinematik', degisken: 'KneeAngles', bilesen: 'X', taraf: 'ipsi', aralik: 'GC', nokta: 101, kod: '' };
  const w = UI.w;
  const gruplar = S.katalog.gruplar.filter(g => !['zu', 'faz'].includes(g.id) && g.degiskenler.length);
  const grup = gruplar.find(g => g.id === w.grup) || gruplar[0];
  w.grup = grup.id;
  if (!grup.degiskenler.some(x => x.id === w.degisken)) w.degisken = (grup.degiskenler.find(x => x.var) || grup.degiskenler[0] || {}).id;
  const d = katalogDegisken(w.degisken);
  const bl = d?.bilesenler || [];
  if (bl.length && !bl.some(x => x.kod === w.bilesen)) w.bilesen = bl[0].kod;
  if (!bl.length) w.bilesen = d?.tur === 'emg' ? 'E' : null;
  if (['kinetik', 'grf'].includes(d?.tur)) w.taraf = 'ipsi';
  const araliklar = S.katalog.araliklar.filter(a => !a.an);
  if (!araliklar.some(a => a.id === w.aralik)) w.aralik = 'GC';
  const yenile = () => render();
  const satir = h('div', { class: 'satir' },
    h('label', { class: 'alan' }, 'Grup', sec(gruplar.map(g => ({ v: g.id, t: g.ad })), w.grup, v => { w.grup = v; yenile(); }, { aria: 'Dalga grubu' })),
    h('label', { class: 'alan', style: { minWidth: '200px' } }, 'Değişken', sec(grup.degiskenler.map(x => ({ v: x.id, t: x.ad })), w.degisken, v => { w.degisken = v; yenile(); }, { aria: 'Dalga değişkeni' })),
    bl.length > 1 ? h('label', { class: 'alan' }, 'Bileşen', sec(bl.map(x => ({ v: x.kod, t: `${x.ad} (${x.kod})` })), w.bilesen, v => { w.bilesen = v; }, { aria: 'Dalga bileşeni' })) : null,
    ['kinematik', 'emg', 'turetilmis'].includes(d?.tur) ? h('label', { class: 'alan' }, 'Taraf', sec([{ v: 'ipsi', t: 'Aynı taraf' }, { v: 'karsi', t: 'Karşı taraf' }], w.taraf, v => { w.taraf = v; })) : null,
    h('label', { class: 'alan', style: { minWidth: '220px' } }, 'Aralık', sec(araliklar.map(a => ({ v: a.id, t: a.ad })), w.aralik, v => { w.aralik = v; }, { aria: 'Dalga aralığı' })),
    h('label', { class: 'alan' }, 'Nokta sayısı', h('input', { type: 'number', min: 2, max: 1001, step: 1, value: w.nokta, onchange: e => { w.nokta = Number(e.target.value || 101); } })),
    h('label', { class: 'alan' }, 'Ad (isteğe bağlı)', h('input', { type: 'text', value: w.kod, placeholder: 'otomatik', style: { width: '180px' }, oninput: e => { w.kod = e.target.value; } })),
    btn('Ekle', async () => { try { await islem('dalga_ekle', { dalga: { ...w } }); w.kod = ''; render(); } catch (e) {} }, { cls: 'ana', ikon: 'arti' }));
  const liste = S.dalgalar.length ? h('table', { class: 'tablo', style: { marginTop: '12px' } }, h('thead', {}, h('tr', {}, ['Ad', 'Değişken', 'Aralık', 'Nokta', ''].map(t => h('th', {}, t)))),
    h('tbody', {}, S.dalgalar.map(x => h('tr', {}, h('td', { class: 'kod' }, x.kod), h('td', {}, x.ozet.degisken, x.ozet.bilesen ? h('div', { class: 'kucuk-yazi' }, x.ozet.bilesen) : null, x.ozet.taraf ? h('div', { class: 'kucuk-yazi' }, x.ozet.taraf) : null),
      h('td', {}, x.ozet.aralik), h('td', { class: 'sayi' }, x.nokta),
      h('td', { class: 'islem' }, h('button', { class: 'btn hayalet tehlike', type: 'button', 'aria-label': 'Sil', onclick: () => islem('dalga_sil', { kod: x.kod }) }, ikon('cop')))))))
    : h('p', { class: 'kucuk-yazi', style: { marginTop: '10px' } }, 'Henüz dalga formu yok.');
  return h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, `Dalga formları (${S.dalgalar.length})`), h('span', { class: 'etiket' }, 'SPM ve grafikler için, isteğe bağlı'),
    h('div', { class: 'bosluk' }), btn('Örnek dalga formları (W9–W12)', () => islem('dalga_paket_ekle'), { cls: 'kucuk', ikon: 'arti' })),
  h('p', { class: 'kucuk-yazi', style: { marginTop: 0 } }, 'Her döngüde seçilen aralık eşit aralıklı noktalara bölünür (ör. 101 nokta = %0–100). Ayrı bir Excel dosyasına döngü ve hasta düzeyinde yazılır; hasta sayfası SPM girdisidir.'),
  satir, liste);
}
function sorguDuzenle(q, i) {
  const d = katalogDegisken(q.degisken);
  UI.b = { aralik: q.aralik || UI.b?.aralik || 'ST', grup: d ? d.grup : 'kinematik', degisken: q.degisken, bilesen: q.bilesen, taraf: q.taraf || 'ipsi',
    ist: q.ist, zb: q.zaman_birimi || '%GC', par: { ...(q.par || {}) }, kod: q.kod, kodElle: true, aciklama: q.aciklama || '', indeks: i };
  render();
  document.getElementById('icerik').scrollTop = 0;
}

async function silOnayli(tur, x) {
  // Kullanılan bir aralık/referans an silinirken onu kullanan sorgular, dalga formları ve tanımlar da silinir; önce sorulur.
  let e;
  try { e = await api('silme_etkisi', { tur, id: x.id }); } catch (err) { return; }
  const kisalt = (l) => l.slice(0, 8).join(', ') + (l.length > 8 ? ' …' : '');
  const kalem = [];
  if (e.sorgular.length) kalem.push(h('li', {}, h('b', {}, `${e.sorgular.length} sorgu`), h('span', { class: 'mono', translate: 'no' }, ': ' + kisalt(e.sorgular))));
  if (e.dalgalar.length) kalem.push(h('li', {}, h('b', {}, `${e.dalgalar.length} dalga formu`), h('span', { class: 'mono', translate: 'no' }, ': ' + kisalt(e.dalgalar))));
  if (e.refler.length) kalem.push(h('li', {}, h('b', {}, `${e.refler.length} referans an`), h('span', { translate: 'no' }, ': ' + kisalt(e.refler))));
  if (e.araliklar.length) kalem.push(h('li', {}, h('b', {}, `${e.araliklar.length} özel aralık`), h('span', { translate: 'no' }, ': ' + kisalt(e.araliklar))));
  if (kalem.length) {
    const govde = h('div', {}, h('p', {}, h('b', { translate: 'no' }, x.ad), h('span', {}, ' kullanılıyor. Silerseniz onunla birlikte şunlar da silinir:')),
      h('ul', { class: 'liste-kucuk' }, kalem), h('p', { class: 'kucuk-yazi' }, 'Yalnızca adını ya da tanımını değiştirmek istiyorsanız silmek yerine "Düzenle" kullanın; sorgular korunur.'));
    if (!(await onayla(tur === 'ref' ? 'Referans anı sil' : 'Aralığı sil', govde, 'Hepsini sil', true))) return;
  }
  if (UI.b && (UI.b.aralik === x.id || UI.b.aralik === '@' + x.id)) UI.b.aralik = 'ST';
  if (UI.b && UI.b.indeks !== null) UI.b = varsayilanB();
  islem(tur === 'ref' ? 'ref_sil' : 'aralik_sil', { id: x.id, zorla: true });
}

function capaEditoru(baslangic, ad) {
  // {tur:'olay'|'yuzde'|'ref', olay, kayma_ms, kayma_gc, yuzde, taban, ref}
  const c = Object.assign({ tur: 'olay', olay: 'IC', kayma_ms: 0, kayma_gc: 0, yuzde: 0, taban: 'GC', ref: '' }, baslangic);
  const kap = h('div', { class: 'adim' });
  const onizleme = h('div', { class: 'capa-onizleme' });
  const refs = () => S.katalog.araliklar.filter(a => a.an && a.id.startsWith('@') && !['@IC', '@CFO', '@CIC', '@FO'].includes(a.id));
  const sayiYaz = (v) => String(Math.abs(v)).replace('.', S.dil === 'en' ? '.' : ',');
  const onizle = () => {
    if (c.tur === 'yuzde') { koy(onizleme); return; }
    const taban = c.tur === 'olay' ? (S.katalog.olaylar.find(o => o.id === c.olay) || {}).ad : (refs().find(a => a.id.slice(1) === c.ref) || {}).ad;
    if (!taban) { koy(onizleme); return; }
    let ek = '';
    if (c.kayma_ms) ek += ` ${c.kayma_ms > 0 ? '+' : '−'} ${sayiYaz(c.kayma_ms)} ms`;
    if (c.kayma_gc) ek += ` ${c.kayma_gc > 0 ? '+' : '−'} ${S.dil === 'en' ? sayiYaz(c.kayma_gc) + '% GC' : '%' + sayiYaz(c.kayma_gc) + ' GC'}`;
    koy(onizleme, '→ ', h('span', {}, taban), h('b', { translate: 'no' }, ek));
  };
  const kaymaAlanlari = () => [
    h('label', { class: 'alan' }, 'Kayma (ms)', h('input', { type: 'number', step: 10, value: c.kayma_ms, 'aria-label': ad + ' kayma ms',
      oninput: e => { c.kayma_ms = Number(e.target.value || 0); onizle(); } })),
    h('label', { class: 'alan' }, 'Kayma (%GC)', h('input', { type: 'number', step: 1, value: c.kayma_gc, 'aria-label': ad + ' kayma GC',
      oninput: e => { c.kayma_gc = Number(e.target.value || 0); onizle(); } }))];
  const ciz = () => {
    const rl = refs();
    if (c.tur === 'ref' && rl.length && !rl.some(a => a.id.slice(1) === c.ref)) c.ref = rl[0].id.slice(1);
    koy(kap, h('div', { class: 'adim-baslik' }, ad),
      h('div', { class: 'segment' }, [['olay', 'Event'], ['yuzde', '% noktası'], ['ref', 'Referans an']].map(([v, t]) =>
        h('button', { type: 'button', class: c.tur === v ? 'aktif' : '', onclick: () => { if (c.tur !== v) { c.kayma_ms = 0; c.kayma_gc = 0; } c.tur = v; ciz(); } }, t))),
      c.tur === 'olay' ? h('div', { class: 'satir' },
        h('label', { class: 'alan' }, 'Event', sec(S.katalog.olaylar.map(o => ({ v: o.id, t: o.ad })), c.olay, v => { c.olay = v; onizle(); })),
        ...kaymaAlanlari()) : null,
      c.tur === 'yuzde' ? h('div', { class: 'satir' },
        h('label', { class: 'alan' }, 'Yüzde', h('input', { type: 'number', step: 0.5, value: c.yuzde, onchange: e => { c.yuzde = Number(e.target.value || 0); } })),
        h('label', { class: 'alan' }, 'Neyin yüzdesi', sec([{ v: 'GC', t: 'Döngü (IC = 0, sonraki IC = 100)' }, { v: 'ST', t: 'Stance (IC → FO)' }, { v: 'SW', t: 'Swing (FO → sonraki IC)' }], c.taban, v => { c.taban = v; }))) : null,
      c.tur === 'ref' ? (rl.length ? h('div', { class: 'satir' },
        h('label', { class: 'alan', style: { minWidth: '200px', flex: 1 } }, 'Referans an', sec(rl.map(a => ({ v: a.id.slice(1), t: a.ad })), c.ref, v => { c.ref = v; onizle(); })),
        ...kaymaAlanlari())
        : h('div', { class: 'not' }, 'Önce bir referans an tanımlayın.')) : null,
      c.tur !== 'yuzde' ? onizleme : null,
      c.tur !== 'yuzde' ? h('div', { class: 'not' }, 'Kayma: pozitif değer sonrasını, negatif değer öncesini gösterir (ör. Foot Off sonrası 100 ms için 100, IC öncesi 100 ms için −100).') : null);
    onizle();
  };
  ciz();
  const kayma = () => ({ ...(c.kayma_ms ? { kayma_ms: c.kayma_ms } : {}), ...(c.kayma_gc ? { kayma_gc: c.kayma_gc } : {}) });
  kap.deger = () => c.tur === 'olay' ? { olay: c.olay, ...kayma() }
    : (c.tur === 'yuzde' ? { yuzde: c.yuzde, taban: c.taban } : { ref: c.ref, ...kayma() });
  return kap;
}
function capaDurumu(c, varsayilan) {
  // kayıtlı çapa sözlüğünü editör durumuna çevirir
  if (!c) return varsayilan;
  if ('olay' in c) return { tur: 'olay', olay: c.olay, kayma_ms: c.kayma_ms || 0, kayma_gc: c.kayma_gc || 0 };
  if ('yuzde' in c) return { tur: 'yuzde', yuzde: c.yuzde, taban: c.taban || 'GC' };
  if ('ref' in c) return { tur: 'ref', ref: c.ref, kayma_ms: c.kayma_ms || 0, kayma_gc: c.kayma_gc || 0 };
  return varsayilan;
}
function ozelAralikModal(mevcut) {
  // mevcut verilirse o aralık düzenlenir (ad ve tanım); sorgular aralığa kimliğiyle bağlı olduğundan korunur
  const hizliOlur = (a) => a && 'yuzde' in a.bas && 'yuzde' in a.son && (a.bas.taban || 'GC') === (a.son.taban || 'GC');
  let mod = !mevcut || hizliOlur(mevcut) ? 'hizli' : 'gelismis';
  const ad = h('input', { type: 'text', placeholder: 'ör. %48–52 GC', style: { width: '100%' }, 'aria-label': 'Aralığın adı' });
  const hb = h('input', { type: 'number', step: 0.5, value: mevcut && hizliOlur(mevcut) ? mevcut.bas.yuzde : 0 }), hs = h('input', { type: 'number', step: 0.5, value: mevcut && hizliOlur(mevcut) ? mevcut.son.yuzde : 2 });
  let taban = mevcut && hizliOlur(mevcut) ? (mevcut.bas.taban || 'GC') : 'GC';
  const tabanSec = sec([{ v: 'GC', t: '% döngü (GC)' }, { v: 'ST', t: '% stance' }, { v: 'SW', t: '% swing' }], taban, v => { taban = v; oto(); });
  const oto = () => { if (!ad.dataset.elle) ad.value = `%${hb.value}–${hs.value} ${({ GC: 'GC', ST: 'stance', SW: 'swing' })[taban]}`; };
  hb.oninput = oto; hs.oninput = oto; ad.oninput = () => { ad.dataset.elle = '1'; };
  if (mevcut) { ad.value = mevcut.ad; ad.dataset.elle = '1'; } else oto();
  const bas = capaEditoru(capaDurumu(mevcut && mevcut.bas, { tur: 'olay', olay: 'IC' }), 'Başlangıç'),
    son = capaEditoru(capaDurumu(mevcut && mevcut.son, { tur: 'olay', olay: 'FO' }), 'Bitiş');
  const govde = h('div', {});
  const kullanan = mevcut ? S.sorgular.filter(q => q.aralik === mevcut.id).length + S.dalgalar.filter(w => w.aralik === mevcut.id).length + S.refler.filter(r => r.aralik === mevcut.id).length : 0;
  const ciz = () => koy(govde,
    h('div', { class: 'segment', style: { marginBottom: '12px' } }, [['hizli', 'Yüzde aralığı'], ['gelismis', 'Event / referans an ile']].map(([v, t]) =>
      h('button', { type: 'button', class: mod === v ? 'aktif' : '', onclick: () => { mod = v; ciz(); } }, t))),
    h('label', { class: 'alan', style: { marginBottom: '12px' } }, 'Aralığın adı', ad),
    mod === 'hizli' ? h('div', {}, h('div', { class: 'satir' }, h('label', { class: 'alan' }, 'Başlangıç %', hb), h('label', { class: 'alan' }, 'Bitiş %', hs),
      h('label', { class: 'alan' }, 'Taban', tabanSec)),
    h('p', { class: 'kucuk-yazi' }, 'Ondalık girebilirsiniz (ör. 48,5–51,5). Başlangıç = bitiş ise o andaki değer alınır. 0\'ın altı ya da 100\'ün üstü komşu döngüye uzanır (ör. −5 ile 0: IC öncesi).'))
      : h('div', { class: 'iki-sutun' }, bas, son),
    kullanan ? h('p', { class: 'kucuk-yazi' }, `Bu aralığı ${kullanan} sorgu / tanım kullanıyor; değişiklik hepsine yansır.`) : null);
  ciz();
  modal({ baslik: mevcut ? 'Özel aralığı düzenle' : 'Yeni özel aralık', genis: true, govde, butonlar: [{ yazi: 'Vazgeç' }, { yazi: mevcut ? 'Kaydet' : 'Ekle', cls: 'ana', tikla: async () => {
    const g = mod === 'hizli' ? { ad: ad.value, bas: { yuzde: Number(hb.value), taban }, son: { yuzde: Number(hs.value), taban } }
      : { ad: ad.value, bas: bas.deger(), son: son.deger() };
    if (mevcut) g.id = mevcut.id;
    const j = await islem('aralik_ekle', g);
    if (!mevcut && UI.b && j.yeni_id) { UI.b.aralik = j.yeni_id; render(); }
  } }] });
}
function refModal(mevcut) {
  // mevcut verilirse o referans an düzenlenir; onu kullanan sorgular ve aralıklar korunur
  const r = mevcut ? { id: mevcut.id, ad: mevcut.ad, grup: (katalogDegisken(mevcut.degisken) || {}).grup || 'kinetik', degisken: mevcut.degisken,
    bilesen: mevcut.bilesen, taraf: mevcut.taraf || 'ipsi', aralik: mevcut.aralik, ekstremum: mevcut.ekstremum || 'max', yumusatma_ms: mevcut.yumusatma_ms || 0 }
    : { ad: '', grup: 'kinetik', degisken: 'AnklePower', bilesen: 'Z', taraf: 'ipsi', aralik: 'ST', ekstremum: 'max', yumusatma_ms: 0 };
  const govde = h('div', {});
  const ciz = () => {
    const grup = S.katalog.gruplar.find(g => g.id === r.grup);
    const degs = grup.degiskenler;
    if (!degs.some(x => x.id === r.degisken)) r.degisken = degs[0]?.id || '';
    const d = katalogDegisken(r.degisken);
    const bl = d?.bilesenler || [];
    if (bl.length && !bl.some(x => x.kod === r.bilesen)) r.bilesen = bl[0].kod;
    if (!bl.length) r.bilesen = d?.tur === 'emg' ? 'E' : null;
    const kendine = new Set(mevcut ? S.ozel_araliklar.filter(a => a.bas.ref === mevcut.id || a.son.ref === mevcut.id).map(a => a.id) : []);
    const araliklar = S.katalog.araliklar.filter(a => !a.an && !kendine.has(a.id));
    koy(govde,
      h('label', { class: 'alan', style: { marginBottom: '12px' } }, 'Adı', h('input', { type: 'text', value: r.ad, placeholder: 'ör. Pik diz fleksör momenti', style: { width: '100%' }, oninput: e => { r.ad = e.target.value; } })),
      h('div', { class: 'segment', style: { marginBottom: '10px' } }, S.katalog.gruplar.filter(g => !['zu', 'faz'].includes(g.id) && g.degiskenler.length).map(g =>
        h('button', { type: 'button', class: r.grup === g.id ? 'aktif' : '', onclick: () => { r.grup = g.id; ciz(); } }, g.ad))),
      h('div', { class: 'satir' },
        h('label', { class: 'alan', style: { minWidth: '240px' } }, 'Değişken', sec(degs.map(x => ({ v: x.id, t: x.ad })), r.degisken, v => { r.degisken = v; ciz(); })),
        bl.length > 1 ? h('label', { class: 'alan' }, 'Bileşen', sec(bl.map(x => ({ v: x.kod, t: `${x.ad} – ${x.isaret}` })), r.bilesen, v => { r.bilesen = v; })) : null,
        ['kinematik', 'emg'].includes(d?.tur) ? h('label', { class: 'alan' }, 'Taraf', sec([{ v: 'ipsi', t: 'Aynı taraf' }, { v: 'karsi', t: 'Karşı taraf' }], r.taraf, v => { r.taraf = v; })) : null),
      h('div', { class: 'satir', style: { marginTop: '10px' } },
        h('label', { class: 'alan', style: { minWidth: '260px' } }, 'Arama aralığı', sec(araliklar.map(a => ({ v: a.id, t: a.ad })), r.aralik, v => { r.aralik = v; })),
        h('label', { class: 'alan' }, 'Aranan', sec([{ v: 'max', t: 'En yüksek değerin anı' }, { v: 'min', t: 'En düşük değerin anı' }], r.ekstremum, v => { r.ekstremum = v; })),
        h('label', { class: 'alan' }, 'Yumuşatma (ms)', h('input', { type: 'number', min: 0, step: 10, value: r.yumusatma_ms, onchange: e => { r.yumusatma_ms = Number(e.target.value || 0); } }))),
      h('p', { class: 'kucuk-yazi' }, 'Tanımlanan an, aralık listesinde "Referans anlar" altında görünür: o andaki herhangi bir değişkeni (ör. kalça ve diz gücü, EMG) çekebilir ya da aralık sınırı olarak kullanabilirsiniz. Kinetik değişkenler yalnızca plakalı döngülerde bulunur.'));
  };
  ciz();
  modal({ baslik: mevcut ? 'Referans anı düzenle' : 'Yeni referans an', genis: true, govde, butonlar: [{ yazi: 'Vazgeç' }, { yazi: mevcut ? 'Kaydet' : 'Ekle', cls: 'ana', tikla: async () => {
    const j = await islem('ref_ekle', { ref: r });
    if (!mevcut && UI.b && j.yeni_id) { UI.b.aralik = j.yeni_id; if (UI.b.ist !== 'deger') UI.b.ist = 'deger'; render(); }
  } }] });
}

/* ================================================================== 4. HASTALAR */
function sHastalar() {
  const hs = S.hastalar;
  if (!hs.length) return [...baslik('Hastalar ve MVIC'), h('div', { class: 'kart bos' }, h('h3', {}, 'Hasta yok'), h('p', {}, 'Önce dosya ekleyin.'))];
  const tutarsiz = hs.filter(x => x.tutarsiz);
  const kaslar = S.katalog.kaslar.filter(k => k.eslesmis);
  const mvicHarita = {};
  for (const m of S.mvic) mvicHarita[m.anahtar] = m.deger;
  const mvicKullan = S.ayarlar.emg.normalizasyon === 'mvic';
  const tablo = h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, h('th', {}, 'Hasta'), h('th', {}, 'Ölçüm tarihi'),
    h('th', { class: 'sayi' }, 'Dosya'), h('th', { class: 'sayi' }, 'Döngü S/Sğ'), h('th', { class: 'sayi' }, 'Kinetik S/Sğ'), h('th', { class: 'sayi' }, 'Kütle (kg)'),
    h('th', { class: 'sayi' }, 'Bacak S/Sğ (mm)'), h('th', {}, 'Etkilenen taraf'))),
  h('tbody', {}, hs.map(x => h('tr', {}, h('td', {}, x.hasta), h('td', {}, x.tarih || h('span', { class: 'etiket uyari' }, 'yok')), h('td', { class: 'sayi' }, x.dahil < x.dosya ? `${x.dahil}/${x.dosya}` : x.dosya),
    h('td', { class: 'sayi' }, `${x.dongu_L} / ${x.dongu_R}`), h('td', { class: 'sayi' }, `${x.kinetik_L} / ${x.kinetik_R}`),
    h('td', { class: 'sayi' }, x.kutle, x.tutarsiz ? h('span', { class: 'etiket uyari', style: { marginLeft: '4px' }, title: 'Trial\'lar arasında kütle ya da bacak uzunluğu farklı (VSK değişmiş olabilir)' }, '!') : null),
    h('td', { class: 'sayi' }, `${x.bacak_L || '–'} / ${x.bacak_R || '–'}`),
    h('td', {}, (() => { const el = sec([{ v: '', t: '— girilmedi —' }, { v: 'L', t: 'Sol' }, { v: 'R', t: 'Sağ' }], x.etkilenen, v => islem('hasta_guncelle', { anahtar: x.anahtar, etkilenen: v }), { aria: 'Etkilenen taraf ' + x.hasta + ' ' + x.tarih });
      el.dataset.anahtar = x.anahtar; return el; })()))))));
  // Taraf kutusu seçiliyken Ctrl+V: tek sütun yapıştırılırsa o satırdan aşağı doldurur; ad + taraf yapıştırılırsa toplu pencere açılır
  tablo.addEventListener('paste', (e) => {
    const el = document.activeElement;
    if (!el || el.tagName !== 'SELECT' || !el.dataset.anahtar) return;
    const metin = (e.clipboardData || window.clipboardData)?.getData('text') || '';
    const satirlar = metin.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
    if (!satirlar.length) return;
    e.preventDefault();
    if (satirlar.some(x => x.includes('\t'))) { topluTarafModal(metin); return; }
    const i0 = hs.findIndex(x => x.anahtar === el.dataset.anahtar);
    const coklu = [], anlasilmayan = [];
    satirlar.forEach((t, k) => {
      const hst = hs[i0 + k]; if (!hst) return;
      const v = tarafCoz(t);
      if (v === null) anlasilmayan.push(t); else coklu.push({ anahtar: hst.anahtar, etkilenen: v });
    });
    if (coklu.length) islem('hasta_guncelle', { coklu }).then(() => bildir(`${coklu.length} satır dolduruldu.` + (anlasilmayan.length ? ` Anlaşılmayan: ${anlasilmayan.slice(0, 4).join(', ')}` : ''), anlasilmayan.length ? '' : 'ok'));
    else bildir('Yapıştırılan değerler taraf olarak anlaşılmadı (Sol / Sağ / L / R).', 'hata');
  });
  const mvicTablo = kaslar.length ? h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, h('th', {}, 'Hasta'), h('th', {}, 'Ölçüm tarihi'),
    ...kaslar.flatMap(k => ['L', 'R'].map(t => h('th', { class: 'sayi' }, `${k.kod} ${TARAF[t]} (µV)`))))),
  h('tbody', {}, hs.map(x => h('tr', {}, h('td', {}, x.hasta), h('td', {}, x.tarih || '–'), ...kaslar.flatMap(k => ['L', 'R'].map(t => {
    const tam = mvicHarita[`${x.mvic_anahtar}|${x.tarih || '*'}|${k.kod}|${t}`];
    const genel = mvicHarita[`${x.mvic_anahtar}|*|${k.kod}|${t}`];
    const deger = tam ?? genel;
    return h('td', { class: 'sayi' }, h('input', { type: 'text', inputmode: 'decimal', value: deger ?? '', style: { width: '90px', minWidth: '0', textAlign: 'right', color: tam === undefined && genel !== undefined ? 'var(--ink-2)' : '' },
      title: tam === undefined && genel !== undefined ? 'Hastanın tüm ölçüm tarihleri için geçerli değer (Excel\'den)' : '',
      'aria-label': `MVIC ${x.hasta} ${k.kod} ${TARAF[t]}`, onchange: e => islem('mvic_guncelle', { hasta: x.hasta, tarih: x.tarih || '*', kas: k.kod, taraf: t, deger: e.target.value }) }));
  }))))))) : h('p', { class: 'kucuk-yazi' }, 'EMG kanalları eşleştirilince burada her kas için MVIC girebilirsiniz.');
  return [...baslik('Hastalar ve MVIC', 'Hastalar, hasta adı ve ölçüm tarihine göre gruplanır. Etkilenen tarafı girerseniz Excel\'e etkilenen/sağlam, fark ve LSI sütunları eklenir. Girmek zorunlu değil; sonra da girebilirsiniz.'),
    tutarsiz.length ? h('div', { class: 'kutu uyari' }, ikon('uyari'), h('div', { class: 'govde-m' }, 'Şu hastalarda trial\'lar arasında kütle ya da bacak uzunluğu farklı (VSK değişmiş ya da başka hastanın VSK\'sı kullanılmış olabilir): ', tutarsiz.map(x => x.hasta).join(', '))) : null,
    h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, `Hastalar (${hs.length})`), h('div', { class: 'bosluk' }),
      btn('Hasta listesini kopyala', hastaListesiKopyala, { cls: 'kucuk', ikon: 'kopya', title: 'Hasta | Tarih | Taraf listesini panoya kopyalar; Excel\'e yapıştırıp tarafları doldurabilirsiniz.' }),
      btn('Tarafları toplu yapıştır…', () => topluTarafModal(''), { cls: 'kucuk', ikon: 'yapistir' })),
      h('p', { class: 'kucuk-yazi', style: { marginTop: 0 } }, 'Etkilenen tarafı tek tek seçebilir, Excel\'den toplu yapıştırabilir ya da bir taraf kutusu seçiliyken Ctrl+V ile o satırdan aşağı doldurabilirsiniz.'), tablo),
    h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, 'MVIC değerleri'), mvicKullan ? h('span', { class: 'etiket ok' }, 'normalizasyonda kullanılıyor')
      : h('span', { class: 'etiket' }, 'şu an kullanılmıyor (Ayarlar → EMG normalizasyonu)'),
    !mvicKullan && S.mvic.length ? btn('%MVIC\'e geç', () => islem('ayarlar_guncelle', { emg: { normalizasyon: 'mvic' } }), { cls: 'kucuk ana' }) : null, h('div', { class: 'bosluk' }),
    btn('Excel\'den içe aktar…', async () => {
      const y = await dosyaSec('ac', { uzanti: 'xlsx', baslik: 'MVIC tablosu (Excel)' }); if (!y.length) return;
      const j = await islem('mvic_ice_aktar', { yol: y[0] });
      if (j.mvic_sor && await onayla('EMG normalizasyonu', 'MVIC değerleri okundu ama EMG normalizasyonu şu an %MVIC değil; bu haliyle EMG değerleri MVIC\'e bölünmeden yazılır. Normalizasyon %MVIC yapılsın mı?', '%MVIC\'e geç'))
        islem('ayarlar_guncelle', { emg: { normalizasyon: 'mvic' } });
    }, { cls: 'kucuk', ikon: 'ac' })),
    h('p', { class: 'kucuk-yazi' }, 'MVIC, yürüyüşle aynı zincirle işlenmiş (aynı filtre + RMS) MVIC kaydının zarf tepesi olmalı (µV). Excel biçimi: Hasta | Taraf | <Kas>_MVIC_uV (tek kas) ya da Hasta | Kas | Taraf | MVIC_uV. "Tarih" sütunu yoksa değer hastanın tüm ölçümlerine uygulanır.'),
    mvicTablo)];
}

function tarafCoz(t) {
  const k = String(t).trim().toLocaleLowerCase('tr').replace(/ğ/g, 'g').replace(/[^a-z]/g, '');
  if (['l', 'left', 'sol', 's', 'sl'].includes(k)) return 'L';
  if (['r', 'right', 'sag', 'sg'].includes(k)) return 'R';
  if (['yok', 'none'].includes(k) || ['-', '—'].includes(String(t).trim())) return '';
  return null;
}
async function panoyaYaz(metin) {
  try { await navigator.clipboard.writeText(metin); return true; } catch (e) {
    const ta = h('textarea', { style: { position: 'fixed', opacity: 0 } }); ta.value = metin; document.body.append(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (e2) {} ta.remove(); return ok;
  }
}
async function hastaListesiKopyala() {
  const en = S.dil === 'en';
  const satirlar = [[en ? 'Patient' : 'Hasta', en ? 'Date' : 'Tarih', en ? 'Side' : 'Taraf'].join('\t'),
    ...S.hastalar.map(x => [x.hasta, x.tarih, x.etkilenen ? (en ? { L: 'Left', R: 'Right' } : { L: 'Sol', R: 'Sağ' })[x.etkilenen] : ''].join('\t'))];
  if (await panoyaYaz(satirlar.join('\n'))) bildir(`${S.hastalar.length} satır panoya kopyalandı. Excel'e yapıştırıp Taraf sütununu doldurun, sonra "Tarafları toplu yapıştır…" ile geri alın.`, 'ok');
  else bildir('Panoya kopyalanamadı.', 'hata');
}
function topluTarafModal(ilkMetin) {
  const alan = h('textarea', { class: 'yapistir-alan', rows: 8, 'aria-label': 'Yapıştırılacak liste', placeholder: 'Ayse Yilmaz\tSol\nMehmet Demir\tSağ\n…', spellcheck: 'false' });
  alan.value = ilkMetin || '';
  const sonuc = h('div', {});
  let son = null, z = null;
  const parcala = (l) => l.includes('\t') ? l.split('\t') : (l.includes(';') ? l.split(';') : ((l.match(/^(.*\S)\s+(\S+)$/) || []).slice(1).length ? l.match(/^(.*\S)\s+(\S+)$/).slice(1) : [l]));
  const satirlar = () => alan.value.split(/\r?\n/).filter(l => l.trim()).map(parcala);
  const etiket = (d) => h('span', { class: 'etiket ' + (d === 'tamam' ? 'ok' : (d === 'zaten aynı' ? '' : 'uyari')) }, d === 'tamam' ? 'değişecek' : d);
  const onizle = async () => {
    const st = satirlar();
    if (!st.length) { son = null; koy(sonuc); return; }
    let j; try { j = await api('hasta_toplu', { satirlar: st }); } catch (e) { return; }
    son = j;
    const o = j.ozet;
    koy(sonuc,
      h('div', { class: 'ozetler', style: { margin: '12px 0' } }, ozet(o.satir, 'satır okundu'), ozet(o.degisecek, 'kayıt değişecek', o.degisecek ? '' : ''), ozet(o.sorunlu, 'eşleşmeyen satır', o.sorunlu ? 'uyari' : ''),
        ozet(o.listede_olmayan.length, 'listede olmayan hasta', '')),
      h('div', { class: 'tablo-kap', style: { maxHeight: '34vh' } }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, ['Hasta (yapıştırılan)', 'Taraf', 'Tarih', 'Eşleşen kayıt', 'Durum'].map(t => h('th', {}, t)))),
        h('tbody', {}, j.satirlar.map(x => h('tr', {}, h('td', { translate: 'no' }, x.hasta), h('td', {}, x.taraf === null ? h('span', { translate: 'no' }, x.taraf_ham || '') : (x.taraf ? TARAF[x.taraf] : '— girilmedi —')),
          h('td', {}, x.tarih || h('span', { class: 'kucuk-yazi' }, 'tüm tarihler')),
          h('td', { translate: 'no' }, x.eslesen.length ? x.eslesen.map(e => e.hasta + (e.tarih ? ` (${e.tarih})` : '')).join(', ') : ''), h('td', {}, etiket(x.durum))))))),
      o.listede_olmayan.length ? h('p', { class: 'kucuk-yazi' }, h('span', {}, 'Yapıştırılan listede olmayan hastalar (tarafları değişmez): '), h('span', { translate: 'no' }, o.listede_olmayan.slice(0, 30).join(', ') + (o.listede_olmayan.length > 30 ? ' …' : ''))) : null);
  };
  alan.addEventListener('input', () => { clearTimeout(z); z = setTimeout(onizle, 250); });
  const govde = h('div', {},
    h('p', { style: { marginTop: 0 } }, 'Excel\'den iki sütun kopyalayıp aşağıya yapıştırın: hasta adı ve taraf (Sol / Sağ, L / R, Left / Right). Üçüncü bir tarih sütunu varsa yalnızca o ölçüm günü güncellenir; yoksa hastanın tüm ölçüm günleri.'),
    h('p', { class: 'kucuk-yazi' }, 'Adlar büyük/küçük harf ve Türkçe karakter farkı gözetilmeden eşleştirilir (Yılmaz = YILMAZ = Yilmaz). Başlık satırı varsa atlanır. Uygulamadan önce aşağıda ne değişeceğini görürsünüz.'),
    alan, sonuc);
  modal({ baslik: 'Etkilenen tarafları toplu yapıştır', genis: true, govde, butonlar: [{ yazi: 'Vazgeç' }, { yazi: 'Uygula', cls: 'ana', tikla: async () => {
    const st = satirlar();
    if (!st.length) { bildir('Önce listeyi yapıştırın.'); return false; }
    if (!son) await onizle();
    if (son && !son.ozet.degisecek) { bildir('Değişecek kayıt yok.'); return false; }
    await islem('hasta_toplu', { satirlar: st, uygula: true });
  } }] });
  if (ilkMetin) onizle();
  setTimeout(() => alan.focus(), 60);
}

/* ================================================================== 5. AYARLAR */
function sAyarlar() {
  const a = S.ayarlar, e = a.emg, d = a.dongu;
  const guncel = (gov) => islem('ayarlar_guncelle', gov);
  const sayi = (deger, degisti, o = {}) => h('input', { type: 'number', value: deger, step: o.step || 'any', min: o.min, style: { width: o.w || '100px' },
    onchange: ev => { const v = ev.target.value; if (v === '' || isNaN(Number(v))) { bildir('Sayı girin.', 'hata'); render(); return; } degisti(Number(v)); } });
  const radyo = (ad, secenekler, deger, degisti) => h('div', {}, secenekler.map(([v, t, alt]) => h('label', { class: 'secenek' },
    h('input', { type: 'radio', name: ad, checked: deger === v, onchange: () => degisti(v) }), h('span', {}, t, alt ? h('small', {}, alt) : null))));
  const kutucuk = (deger, t, degisti, alt) => h('label', { class: 'secenek' }, h('input', { type: 'checkbox', checked: deger, onchange: ev => degisti(ev.target.checked) }), h('span', {}, t, alt ? h('small', {}, alt) : null));
  return [...baslik('Ayarlar', 'Bu ayarlar projeyle birlikte kaydedilir ve Excel\'deki "Yöntem" sayfasına yazılır.',
    btn('Varsayılanlara dön', async () => { if (await onayla('Ayarlar', 'Tüm ayarlar varsayılana dönsün mü? (EMG eşleştirmeleri ve MVIC değerleri korunur.)')) islem('ayarlari_sifirla'); }, { cls: 'hayalet' })),
  h('div', { class: 'kart' }, h('h2', {}, 'Dil'),
    radyo('dil', [['tr', 'Türkçe', 'Arayüz, uyarılar ve Excel çıktısı Türkçe.'], ['en', 'English', 'Interface, warnings and Excel output in English.']],
      S.dil, v => dilDegistir(v))),
  h('div', { class: 'kart' }, h('h2', {}, 'Event zamanları ve döngüler'),
    radyo('zaman', [[false, 'C3D\'deki event zamanı (önerilen)', 'Aralık sınırlarındaki değer komşu kareler arasından interpolasyonla alınır; kareye yuvarlama hatası olmaz.'],
      [true, 'En yakın kareye yuvarla', 'Kare bazlı çalışan başka bir yöntemle karşılaştırma için.']], d.kareye_yuvarla, v => guncel({ dongu: { kareye_yuvarla: v } })),
    h('h3', {}, 'Olağan dışı durum uyarıları (yalnızca uyarı yazılır, değer hesaplanır)'),
    h('div', { class: 'ayar-izgara' },
      h('label', { class: 'alan' }, 'Stride süresi (s)', h('div', { class: 'satir' }, sayi(d.stride_aralik[0], v => guncel({ dongu: { stride_aralik: [v, d.stride_aralik[1]] } }), { step: 0.1, w: '80px' }), '–', sayi(d.stride_aralik[1], v => guncel({ dongu: { stride_aralik: [d.stride_aralik[0], v] } }), { step: 0.1, w: '80px' }))),
      h('label', { class: 'alan' }, 'Stance oranı (%)', h('div', { class: 'satir' }, sayi(Math.round(d.stance_oran[0] * 100), v => guncel({ dongu: { stance_oran: [v / 100, d.stance_oran[1]] } }), { w: '80px' }), '–', sayi(Math.round(d.stance_oran[1] * 100), v => guncel({ dongu: { stance_oran: [d.stance_oran[0], v / 100] } }), { w: '80px' }))),
      h('label', { class: 'alan' }, '1. çift destek en fazla (%GC)', sayi(Math.round(d.ds1_max_oran * 100), v => guncel({ dongu: { ds1_max_oran: v / 100 } }))),
      h('label', { class: 'alan' }, 'Geçersiz döngü: stride kısaysa (s)', sayi(d.min_stride, v => guncel({ dongu: { min_stride: v } }), { step: 0.05 }), h('span', { class: 'ipucu' }, 'Çift işaretlenmiş event; değer hesaplanmaz.')),
      h('label', { class: 'alan' }, 'Kinetik döngü eşiği (N/kg)', sayi(d.kinetik_esik, v => guncel({ dongu: { kinetik_esik: v } }), { step: 0.5 }), h('span', { class: 'ipucu' }, 'Stance\'te GRF bu değeri aşarsa plakalı sayılır.')))),
  h('div', { class: 'kart' }, h('h2', {}, 'Eksik veri ve notlar'),
    radyo('eksik', [['bos', 'Aralıkta eksik örnek varsa değeri boş bırak (önerilen)', 'GRF\'de stance içi boşluk, EMG paket kaybı, marker boşluğu gibi.'],
      ['hesapla', 'Mevcut örneklerle hesapla ve uyar', 'Eksik kısım tepeyi gizleyebilir; dikkatli kullanın.']], a.eksik_veri, v => guncel({ eksik_veri: v })),
    kutucuk(a.sinir_uyarisi, 'Tepe aralığın ilk ya da son örneğindeyse not yaz', v => guncel({ sinir_uyarisi: v }), 'Eğri aralık bittiğinde hâlâ yükseliyorsa değer gerçek bir tepe olmayabilir.'),
    h('h3', {}, 'Lob istatistikleri ve kinetik bütünlük'),
    h('div', { class: 'ayar-izgara' },
      h('label', { class: 'alan' }, 'En kısa lob (%GC)', sayi(a.lob_min_gc, v => guncel({ lob_min_gc: v }), { step: 0.5, min: 0 }),
        h('span', { class: 'ipucu' }, '"İlk pozitif / negatif lob" aranırken bundan kısa süren loblar (sıfır çevresindeki gürültü) atlanır. 0 = hiçbirini atlama.')),
      h('label', { class: 'alan' }, 'Taraf başına en az kinetik döngü', sayi(a.min_kinetik, v => guncel({ min_kinetik: v }), { step: 1, min: 1 }),
        h('span', { class: 'ipucu' }, 'Hasta + tarih için bir tarafta bundan az kinetik döngü varsa Excel\'de Kinetik_Tamam = 0 olur ve Hata olarak listelenir. Satır çıktıdan çıkarılmaz.')))),
  h('div', { class: 'kart' }, h('h2', {}, 'EMG işleme'), h('p', { class: 'kucuk-yazi' }, 'Şu anki zincir: ', h('b', {}, S.emg_zincir)),
    h('div', { class: 'ayar-izgara' },
      h('label', { class: 'alan' }, 'High-pass (Hz)', sayi(e.hp, v => guncel({ emg: { hp: v } }))),
      h('label', { class: 'alan' }, 'Low-pass (Hz)', sayi(e.lp, v => guncel({ emg: { lp: v } }))),
      h('label', { class: 'alan' }, 'Butterworth derecesi', sayi(e.derece, v => guncel({ emg: { derece: Math.max(1, Math.round(v)) } }), { step: 1, min: 1 })),
      h('label', { class: 'alan' }, 'Zarf', sec([{ v: 'rms', t: 'Hareketli RMS' }, { v: 'lineer', t: 'Lineer zarf (doğrultma + alçak geçiren)' }], e.zarf, v => guncel({ emg: { zarf: v } }))),
      e.zarf === 'rms' ? h('label', { class: 'alan' }, 'RMS penceresi (ms)', sayi(e.rms_ms, v => guncel({ emg: { rms_ms: v } }))) : h('label', { class: 'alan' }, 'Zarf alçak geçiren (Hz)', sayi(e.lineer_lp, v => guncel({ emg: { lineer_lp: v } }))),
      h('label', { class: 'alan' }, 'Normalizasyon', sec([{ v: 'yok', t: 'Yok (µV)' }, { v: 'mvic', t: '%MVIC' }, { v: 'dinamik_tepe', t: 'Dinamik: döngü tepelerinin ortalaması' }, { v: 'dinamik_ort', t: 'Dinamik: döngü ortalamalarının ortalaması' }], e.normalizasyon, v => guncel({ emg: { normalizasyon: v } })),
        h('span', { class: 'ipucu' }, 'Dinamik: hasta-tarih-taraf için yürüyüşün kendisine göre %. Etkilenen tarafta MVIC submaksimal kalabiliyorsa tercih edilir; taraflar arası şiddet karşılaştırmasına izin vermez.'))),
    h('div', { class: 'satir', style: { marginTop: '8px' } },
      kutucuk(e.notch, `${e.notch_hz} Hz çentik filtre (+ harmonikleri)`, v => guncel({ emg: { notch: v } })),
      kutucuk(e.ham_uv_yaz, 'Normalize edilmiş değerlerin yanında ham µV sütunlarını da yaz', v => guncel({ emg: { ham_uv_yaz: v } }))),
    h('h3', {}, 'Veri kaybı ve aktivasyon'),
    h('div', { class: 'ayar-izgara' },
      h('label', { class: 'alan' }, 'Veri kaybı: sabit değer en az (ms)', sayi(e.kayip_min_ms, v => guncel({ emg: { kayip_min_ms: v } })), h('span', { class: 'ipucu' }, 'Kablosuz paket kaybında sinyal sabit kalır.')),
      h('label', { class: 'alan' }, 'Eşik: taban + k × SD (k)', sayi(e.esik_sd, v => guncel({ emg: { esik_sd: v } }), { step: 0.5 })),
      h('label', { class: 'alan' }, 'Eşik tabanı (% tepe)', sayi(Math.round(e.esik_taban_tepe * 1000) / 10, v => guncel({ emg: { esik_taban_tepe: v / 100 } }), { step: 1 })),
      h('label', { class: 'alan' }, 'Sessiz pencere (ms)', sayi(e.sessiz_ms, v => guncel({ emg: { sessiz_ms: v } }))),
      h('label', { class: 'alan' }, 'En kısa aktif bölge (ms)', sayi(e.min_aktif_ms, v => guncel({ emg: { min_aktif_ms: v } }))),
      h('label', { class: 'alan' }, 'Birleştirilecek boşluk (ms)', sayi(e.birlestir_ms, v => guncel({ emg: { birlestir_ms: v } }))))),
  h('div', { class: 'kart' }, h('h2', {}, 'Zamansal-uzamsal'),
    h('label', { class: 'alan', style: { maxWidth: '320px' } }, 'Adım uzunluğu için marker', sec([{ v: 'HEE', t: 'HEE (topuk)' }, { v: 'ANK', t: 'ANK (lateral malleol)' }, { v: 'TOE', t: 'TOE' }], a.topuk_marker, v => guncel({ topuk_marker: v })))),
  h('div', { class: 'kart' }, h('h2', {}, 'Ortalamalar ve uç değerler'),
    radyo('ort', [['dongu', 'Hasta ortalaması: tüm döngülerin ortalaması', 'Her döngü eşit ağırlıklı.'],
      ['trial', 'Hasta ortalaması: trial ortalamalarının ortalaması', 'Her trial eşit ağırlıklı.']], a.ortalama_yontemi, v => guncel({ ortalama_yontemi: v })),
    h('label', { class: 'alan', style: { maxWidth: '320px', marginTop: '8px' } }, 'Uç değer eşiği (robust z)', sayi(a.uc_esik, v => guncel({ uc_esik: v }), { step: 0.5 }),
      h('span', { class: 'ipucu' }, 'Uç değerler silinmez, yalnızca Excel\'de listelenir.')))];
}

/* ================================================================== 6. ÇALIŞTIR */
function sCalistir() {
  const c = S.cikti;
  const dahil = S.dosyalar.filter(x => x.dahil);
  const hastaSay = new Set(dahil.map(x => x.hasta + '|' + x.tarih)).size;
  const emgQ = [...S.sorgular, ...S.dalgalar].filter(q => q.degisken.startsWith('EMG:'));
  const eslesmis = new Set(S.kanallar.filter(k => k.kas).map(k => k.kas));
  const eksikKas = [...new Set(emgQ.map(q => q.degisken.slice(4)))].filter(k => !eslesmis.has(k));
  const kontroller = [
    [dahil.length > 0, `${dahil.length} dosya, ${hastaSay} hasta + tarih`],
    [S.sorgular.length > 0 || S.dalgalar.length > 0, `${S.sorgular.length} sorgu` + (S.dalgalar.length ? `, ${S.dalgalar.length} dalga formu` : '')],
  ];
  if (emgQ.length) kontroller.push([!eksikKas.length, eksikKas.length ? `Eşleştirilmemiş kas: ${eksikKas.join(', ')}` : 'EMG kasları eşleştirilmiş']);
  if (emgQ.length && S.ayarlar.emg.normalizasyon === 'mvic') {
    const n = S.mvic.length; kontroller.push([n > 0, n ? `${n} MVIC değeri girilmiş` : 'MVIC normalizasyonu seçili ama MVIC değeri yok']);
  }
  const tarihsiz = dahil.filter(x => !x.tarih).length;
  if (tarihsiz) kontroller.push([false, `${tarihsiz} dosyada ölçüm tarihi yok`]);
  // EMG genlik sorgusu var ama normalizasyon seçilmemiş: değerler µV yazılır, hastalar arası karşılaştırılamaz
  const genlikIst = new Set(S.katalog.genlik_ist || []);
  const emgGenlik = S.sorgular.filter(q => q.degisken.startsWith('EMG:') && genlikIst.has(q.ist)).length + S.dalgalar.filter(w => w.degisken.startsWith('EMG:')).length;
  const emgNormYok = emgGenlik > 0 && S.ayarlar.emg.normalizasyon === 'yok';
  if (emgNormYok) kontroller.push([false, `EMG normalizasyonu seçilmemiş: ${emgGenlik} EMG genlik değişkeni µV olarak yazılacak`]);
  const emgKutu = emgNormYok ? h('div', { class: 'kutu uyari' }, ikon('uyari'), h('div', { class: 'govde-m' },
    h('b', {}, 'EMG normalizasyonu seçilmemiş. '), `${emgGenlik} EMG genlik değişkeni ham µV olarak yazılacak; µV değerleri hastalar ve kaslar arasında karşılaştırılamaz. `,
    S.mvic.length ? `Projede ${S.mvic.length} MVIC değeri var ama kullanılmıyor.` : 'MVIC değerlerini "Hastalar ve MVIC" sayfasından girebilir ya da dinamik normalizasyon seçebilirsiniz.'),
    h('div', { class: 'btn-grup' }, S.mvic.length ? btn('%MVIC\'e geç', () => islem('ayarlar_guncelle', { emg: { normalizasyon: 'mvic' } }), { cls: 'kucuk ana' }) : null,
      btn('Ayarları aç', () => { UI.sayfa = 'ayarlar'; render(); }, { cls: 'kucuk' }))) : null;
  const calisiyor = S.is.calisiyor && S.is.tur === 'calistir';
  const klasorInp = h('input', { type: 'text', value: c.klasor || S.varsayilan_klasor || '', style: { flex: 1, minWidth: '320px' }, 'aria-label': 'Çıktı klasörü',
    onchange: e => islem('ayarlar_guncelle', { cikti: { klasor: e.target.value } }) });
  const adInp = h('input', { type: 'text', value: c.dosya_adi || 'KADEM_Sonuclar.xlsx', style: { width: '320px' }, 'aria-label': 'Dosya adı',
    onchange: e => islem('ayarlar_guncelle', { cikti: { dosya_adi: e.target.value } }) });
  const ayar = h('div', { class: 'kart' }, h('h2', {}, 'Çıktı'),
    h('div', { class: 'satir' }, h('label', { class: 'alan', style: { flex: 1 } }, 'Klasör', h('div', { class: 'satir', style: { gap: '6px', flexWrap: 'nowrap' } }, klasorInp,
      btn('Seç…', async () => { const y = await dosyaSec('klasor', { baslik: 'Çıktı klasörü', baslangic: klasorInp.value }); if (y.length) islem('ayarlar_guncelle', { cikti: { klasor: y[0] } }); }, { ikon: 'klasor' }))),
    h('label', { class: 'alan' }, 'Excel dosyasının adı', adInp)),
    h('label', { class: 'secenek', style: { marginTop: '8px' } }, h('input', { type: 'checkbox', checked: !!c.anonim, onchange: e => islem('ayarlar_guncelle', { cikti: { anonim: e.target.checked } }) }),
      h('span', {}, 'Hasta adlarını kodla (P001, P002…)', h('small', {}, 'Paylaşım için. Ad–kod anahtarı ayrı bir Excel dosyasına yazılır; onu paylaşmayın.'))),
    h('div', { class: 'ayrac' }),
    h('div', { class: 'satir', style: { alignItems: 'center' } },
      h('ul', { class: 'liste-kucuk', style: { flex: 1, listStyle: 'none', paddingLeft: 0 } }, kontroller.map(([ok, t]) => h('li', {}, h('span', { class: 'etiket ' + (ok ? 'ok' : 'uyari'), style: { marginRight: '6px' } }, ok ? '✓' : '!'), t))),
      calisiyor ? btn('İptal', () => api('iptal'), { cls: 'tehlike' }) : null,
      btn('Çalıştır', () => calistirTikla(klasorInp.value, adInp.value), { cls: 'ana buyuk', ikon: 'oynat', disabled: S.is.calisiyor || !dahil.length || !(S.sorgular.length || S.dalgalar.length) })),
    calisiyor ? h('div', { id: 'calistir-ilerleme', style: { marginTop: '14px' } }, ilerlemeCubugu()) : null);
  return [...baslik('Çalıştır ve sonuçlar', 'Program her döngüde sorguları hesaplar, döngü → hasta ortalamalarını alır ve tek bir Excel dosyası yazar. Değerler düzeltilmez; şüpheli her durum "Uyarılar" sayfasına yazılır.'),
    emgKutu, ayar, S.son_sonuc ? sonucBolumu(S.son_sonuc) : null];
}
async function calistirTikla(klasor, ad) {
  // Aynı adla çıktı varsa üzerine yazmadan önce sorulur; varsayılan, sonuna _2, _3 … eklenmiş yeni addır
  let k;
  try { k = await api('cikti_kontrol', { klasor, dosya_adi: ad }); } catch (e) { return; }
  let dosyaAdi = ad;
  if (k.mevcut.length) {
    const secim = await new Promise(res => {
      modal({ baslik: 'Bu adla bir çıktı zaten var', kapaninca: () => res(null),
        govde: h('div', {}, h('p', { style: { marginTop: 0 } }, 'Çıktı klasöründe şu dosyalar zaten var:'),
          h('ul', { class: 'liste-kucuk' }, k.mevcut.map(m => h('li', { class: 'mono', translate: 'no' }, m))),
          h('p', {}, 'Üzerine yazarsanız eski sonuçlar kaybolur. Yeni adla kaydederseniz eski dosyalar korunur; dalga formu ve anahtar dosyaları da aynı eki alır.'),
          h('p', {}, h('span', {}, 'Önerilen yeni ad: '), h('b', { class: 'mono', translate: 'no' }, k.oneri))),
        butonlar: [{ yazi: 'Vazgeç', tikla: () => res(null) }, { yazi: 'Üzerine yaz', cls: 'tehlike', tikla: () => res('yaz') },
          { yazi: 'Yeni adla kaydet', cls: 'ana', tikla: () => res('yeni') }] });
    });
    if (!secim) return;
    if (secim === 'yeni') dosyaAdi = k.oneri;
  }
  islem('calistir', { klasor, dosya_adi: dosyaAdi });
}

function sonucBolumu(r) {
  const o = r.ozet, s = r.sayim || {};
  const dosyaAdi = (r.yol || '').split(/[\\/]/).pop();
  const ust = h('div', { class: 'kart' }, h('div', { class: 'kart-ust' }, h('h2', {}, `Son çalıştırma (${r.zaman})`), h('span', { class: 'kucuk-yazi mono', title: r.yol }, dosyaAdi), h('div', { class: 'bosluk' }),
    btn('Excel\'i aç', () => api('isletim_ac', { yol: r.yol }), { cls: 'ana', ikon: 'disari' }), btn('Klasörü aç', () => api('isletim_ac', { yol: r.klasor }), { ikon: 'klasor' }),
    o.dalga_yol ? btn('Dalga formları', () => api('isletim_ac', { yol: o.dalga_yol }), { ikon: 'disari', title: o.dalga_yol }) : null,
    o.anahtar ? btn('Anahtar dosyası', () => api('isletim_ac', { yol: o.anahtar }), { cls: 'hayalet' }) : null),
  h('div', { class: 'ozetler' }, ozet(o.hasta, 'hasta + tarih'), ozet(o.dongu - o.dislanan, 'kullanılan döngü'), ozet(o.dislanan, 'dışlanan döngü'),
    ozet(s['Hata'] || 0, 'hata', s['Hata'] ? 'hata' : ''), ozet(s['Uyarı'] || 0, 'uyarı', s['Uyarı'] ? 'uyari' : ''), ozet(s['Bilgi'] || 0, 'bilgi notu'), ozet(o.uc_deger, 'uç değer')));
  const ke = o.kinetik_eksik || [];
  let kinKutu = null;
  if (ke.length) {
    const grup = new Map();
    for (const x of ke) { const a = `${x.hasta}|${x.tarih}`; if (!grup.has(a)) grup.set(a, { hasta: x.hasta, tarih: x.tarih, t: [] }); grup.get(a).t.push(x); }
    kinKutu = h('div', { class: 'kutu hata' }, ikon('uyari'), h('div', { class: 'govde-m' },
      h('b', {}, `${grup.size} hasta + tarihte kinetik döngü eksik. `),
      `Bir tarafta en az ${o.min_kinetik || 1} kinetik (kuvvet plakalı) döngü yok; bu ölçümler Excel'de Kinetik_Tamam = 0 olarak işaretlendi, çıktıdan çıkarılmadı. Döngü aslında varsa Nexus'ta plaka atamasını kontrol edip yeniden çalıştırın.`,
      h('ul', { class: 'liste-kucuk', style: { marginTop: '6px' } }, [...grup.values()].slice(0, 40).map(g => h('li', {}, h('b', { translate: 'no' }, g.hasta + (g.tarih ? ` (${g.tarih})` : '')), h('span', { translate: 'no' }, ': '),
        g.t.map((x, i) => [i ? h('span', { translate: 'no' }, ', ') : null, h('span', {}, x.taraf === 'L' ? 'sol' : 'sağ'), h('span', { translate: 'no' }, ` ${x.n}`)])))),
      grup.size > 40 ? h('p', { class: 'kucuk-yazi' }, 'Tamamı Excel\'in "5_Uyarilar" sayfasında.') : null));
  }
  const sekmeler = [['uyarilar', `Uyarılar (${r.uyari_toplam})`], ['uc', `Uç değerler (${r.uc.length})`], ['donguler', 'Döngüleri dışla'], ['onizleme', 'Hasta tablosu önizleme']];
  const sk = h('div', { class: 'sekmeler', role: 'tablist' }, sekmeler.map(([id, t]) => h('button', { type: 'button', class: UI.sonucSekme === id ? 'aktif' : '', onclick: () => { UI.sonucSekme = id; render(); } }, t)));
  let icerik;
  if (UI.sonucSekme === 'uc') icerik = r.uc.length ? h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, ['Düzey', 'Hasta', 'Dosya', 'Taraf', 'Döngü', 'Değişken', 'Değer', 'Karşılaştırma (medyan)', 'Robust z'].map(t => h('th', {}, t)))),
    h('tbody', {}, r.uc.map(u => h('tr', {}, h('td', {}, u.Duzey), h('td', {}, u.Hasta), h('td', {}, u.Dosya), h('td', {}, u.Taraf), h('td', { class: 'sayi' }, u.Dongu ?? ''),
      h('td', { class: 'kod' }, u.Degisken), h('td', { class: 'sayi' }, fmt(u.Deger, 3)), h('td', { class: 'sayi' }, fmt(u.Medyan, 3)), h('td', { class: 'sayi' }, fmt(u.Robust_z, 1)))))))
    : h('p', { class: 'kucuk-yazi' }, 'Uç değer bulunmadı.');
  else if (UI.sonucSekme === 'donguler') icerik = dongulerSekmesi(r);
  else if (UI.sonucSekme === 'onizleme') {
    const p = r.onizleme;
    icerik = h('div', {}, h('p', { class: 'kucuk-yazi' }, `İlk ${p.satirlar.length} satır, ${p.sutunlar.length}/${p.toplam_sutun || p.sutunlar.length} sütun. Tamamı Excel'in "1_Hasta_Duzeyi" sayfasında.`),
      h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo dar' }, h('thead', {}, h('tr', {}, p.sutunlar.map(c => h('th', {}, c)))),
        h('tbody', {}, p.satirlar.map(row => h('tr', {}, row.map(v => h('td', { class: typeof v === 'number' ? 'sayi' : '' }, fmt(v, 3)))))))));
  } else {
    const f = UI.uyariFiltre;
    const ara = (f.ara || '').toLocaleLowerCase('tr');
    const liste = r.uyarilar.filter(u => f[u.onem] && (!ara || (u.dosya + ' ' + u.mesaj + ' ' + u.kod).toLocaleLowerCase('tr').includes(ara)));
    icerik = h('div', {}, h('div', { class: 'satir', style: { marginBottom: '10px', alignItems: 'center' } },
      ['Hata', 'Uyarı', 'Bilgi'].map(o => h('label', { class: 'secenek' }, h('input', { type: 'checkbox', checked: f[o], onchange: e => { f[o] = e.target.checked; render(); } }), onemEtiket(o), ` ${s[o] || 0}`)),
      h('input', { type: 'search', placeholder: 'Ara', value: f.ara, style: { width: '240px', marginLeft: 'auto' }, onchange: e => { f.ara = e.target.value; render(); } })),
    r.uyari_toplam > r.uyarilar.length ? h('p', { class: 'kucuk-yazi' }, `İlk ${r.uyarilar.length} kayıt gösteriliyor; tamamı Excel'in "5_Uyarilar" sayfasında.`) : null,
    h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, ['Önem', 'Dosya', 'Taraf', 'Döngü', 'Kod', 'Açıklama'].map(t => h('th', {}, t)))),
      h('tbody', {}, liste.slice(0, 800).map(u => h('tr', {}, h('td', {}, onemEtiket(u.onem)), h('td', {}, u.dosya), h('td', {}, u.taraf), h('td', { class: 'sayi' }, u.dongu),
        h('td', { class: 'kod' }, u.kod), h('td', {}, u.mesaj)))))));
  }
  return [ust, kinKutu, h('div', { class: 'kart' }, sk, icerik)];
}
function dongulerSekmesi(r) {
  const hastalar = [...new Set(r.donguler.map(d => d.hasta))];
  if (!UI.dongulerHasta || !hastalar.includes(UI.dongulerHasta)) UI.dongulerHasta = hastalar[0] || '';
  const dis = {};
  for (const x of S.dislamalar) dis[`${x.dosya}|${x.taraf}|${x.dongu}`] = x.neden;
  const liste = r.donguler.filter(d => d.hasta === UI.dongulerHasta);
  return h('div', {}, h('p', { class: 'kucuk-yazi' }, 'Dışladığınız döngüler ortalamalara girmez ve Excel\'de gerekçesiyle listelenir. Değişiklik bir sonraki çalıştırmada uygulanır.'),
    h('div', { class: 'satir', style: { marginBottom: '10px' } }, h('label', { class: 'alan' }, 'Hasta', sec(hastalar.map(x => ({ v: x, t: x })), UI.dongulerHasta, v => { UI.dongulerHasta = v; render(); }))),
    h('div', { class: 'tablo-kap' }, h('table', { class: 'tablo' }, h('thead', {}, h('tr', {}, ['Dosya', 'Taraf', 'Döngü', 'Kinetik', 'Dışla', 'Gerekçe'].map(t => h('th', {}, t)))),
      h('tbody', {}, liste.map(d => {
        const k = `${d.dosya}|${d.taraf}|${d.dongu}`;
        const kullanici = k in dis;
        const gecersiz = d.dislandi && !kullanici;
        return h('tr', { class: kullanici || gecersiz ? 'soluk' : '' }, h('td', {}, d.dosya), h('td', {}, TARAF[d.taraf]), h('td', { class: 'sayi' }, d.dongu), h('td', {}, d.kinetik ? '✓' : ''),
          h('td', {}, gecersiz ? h('span', { class: 'etiket hata', title: d.neden }, 'geçersiz') : h('input', { type: 'checkbox', checked: kullanici, 'aria-label': 'Dışla',
            onchange: e => islem('dislama', { dosya: d.dosya, taraf: d.taraf, dongu: d.dongu, dislandi: e.target.checked, neden: dis[k] || '' }) })),
          h('td', {}, kullanici ? h('input', { type: 'text', value: dis[k], placeholder: 'gerekçe', onchange: e => islem('dislama', { dosya: d.dosya, taraf: d.taraf, dongu: d.dongu, dislandi: true, neden: e.target.value }) })
            : (gecersiz ? d.neden : '')));
      })))));
}

/* ------------------------------------------------------------------ proje işlemleri */
async function kaydedilmemisSor() {
  if (!S?.proje?.degisti) return true;
  return onayla('Kaydedilmemiş değişiklikler', 'Projede kaydedilmemiş değişiklikler var. Devam edilirse kaybolacak.', 'Devam et', true);
}
async function projeYeni() { if (await kaydedilmemisSor()) { UI.secili.clear(); UI.b = null; islem('yeni'); } }
async function projeAc() {
  if (!(await kaydedilmemisSor())) return;
  const y = await dosyaSec('ac', { uzanti: 'c3dproj', baslik: 'Proje açın' });
  if (y.length) { UI.secili.clear(); UI.b = null; islem('ac', { yol: y[0] }); }
}
async function projeKaydet(farkli) {
  if (!farkli && S.proje.yol) return islem('kaydet', {});
  const y = await dosyaSec('kaydet', { uzanti: 'c3dproj', baslik: 'Projeyi kaydedin', dosyaAdi: (S.proje.yol ? S.proje.ad : 'Yeni proje') + '.c3dproj' });
  if (y.length) { await islem('kaydet', { yol: y[0] }); bildir('Proje kaydedildi.', 'ok'); }
}
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); projeKaydet(false); }
});
window.addEventListener('beforeunload', (e) => { if (S?.proje?.degisti && !UI.dilYukleniyor) { e.preventDefault(); e.returnValue = ''; } });

/* ------------------------------------------------------------------ başlat */
(async function baslat() {
  try { S = await api('durum'); } catch (e) {
    koy(document.getElementById('icerik'), h('div', { class: 'kart bos' }, h('h3', {}, 'Programa bağlanılamadı'),
      h('p', {}, 'Bu pencereyi kapatıp programı yeniden başlatın.')));
    return;
  }
  await dilHazirla();
  render();
  if (S.is.calisiyor) yokla();
})();
