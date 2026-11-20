(() => {
  const KEY = 'fink-variant';
  const figs = [...document.querySelectorAll('main figure')];
  const chips = [...document.querySelectorAll('[data-variant]')];
  let variant = 'rot';

  function setVariant(v) {
    variant = v;
    chips.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.variant === v)));
    figs.forEach(f => {
      if (!f.dataset[v]) return;
      const [s, l, pdf] = JSON.parse(f.dataset[v]);
      const img = f.querySelector('img');
      img.srcset = `img/${s} 900w, img/${l} ${Math.max(+img.getAttribute('width'), +img.getAttribute('height'))}w`;
      img.src = `img/${s}`;
      img.dataset.large = `img/${l}`;
      f.querySelector('.pdf').href = `pdf/${pdf}`;
    });
    try { localStorage.setItem(KEY, v); } catch (e) {}
    if (viewer.classList.contains('open')) show(cur, true);
  }

  // Overlay
  const viewer = document.getElementById('viewer'), stage = document.getElementById('stage'), vimg = document.getElementById('vimg');
  const $ = id => document.getElementById(id);
  let cur = 0, k = 1, tx = 0, ty = 0, nw = 1, nh = 1, fitK = 1, lastFocus = null, loadToken = 0;
  const apply = () => { vimg.style.transform = `translate(${tx}px,${ty}px) scale(${k})`; };

  function fit() {
    const r = stage.getBoundingClientRect();
    fitK = Math.min(r.width / nw, r.height / nh) * 0.96;
    k = fitK; tx = (r.width - nw * k) / 2; ty = (r.height - nh * k) / 2; apply();
  }
  function zoomAt(f, x, y) {
    const nk = Math.min(Math.max(k * f, fitK * 0.5), 4);
    tx = x - (x - tx) * nk / k; ty = y - (y - ty) * nk / k; k = nk; apply();
  }
  function zoomCenter(f) { const r = stage.getBoundingClientRect(); zoomAt(f, r.width / 2, r.height / 2); }

  function show(i, keepView) {
    cur = (i + figs.length) % figs.length;
    const f = figs[cur], img = f.querySelector('img'), pdf = f.querySelector('.pdf');
    $('vtitle').textContent = f.dataset.title;
    $('vscale').textContent = f.dataset.scale;
    $('vcount').textContent = `${cur + 1} / ${figs.length}`;
    $('vpdf').hidden = !pdf; if (pdf) $('vpdf').href = pdf.href;
    nw = +img.getAttribute('width'); nh = +img.getAttribute('height');
    vimg.style.width = nw + 'px'; vimg.style.height = nh + 'px';
    vimg.alt = img.alt;
    vimg.src = img.currentSrc || img.src;
    const token = ++loadToken, big = new Image();
    $('vload').hidden = false;
    big.onload = () => { if (token === loadToken) { vimg.src = big.src; $('vload').hidden = true; } };
    big.onerror = () => { if (token === loadToken) $('vload').hidden = true; };
    big.src = img.dataset.large;
    if (!keepView) fit();
  }
  function open(i) {
    lastFocus = document.activeElement;
    viewer.classList.add('open');
    document.body.style.overflow = 'hidden';
    show(i);
    $('vclose').focus();
  }
  function close() {
    viewer.classList.remove('open');
    document.body.style.overflow = '';
    loadToken++;
    if (lastFocus) lastFocus.focus();
  }

  figs.forEach((f, i) => f.querySelector('.sheet').addEventListener('click', () => open(i)));
  $('vclose').onclick = close;
  $('vprev').onclick = () => show(cur - 1);
  $('vnext').onclick = () => show(cur + 1);
  $('vin').onclick = () => zoomCenter(1.5);
  $('vout').onclick = () => zoomCenter(1 / 1.5);
  $('vfit').onclick = fit;
  window.addEventListener('resize', () => { if (viewer.classList.contains('open')) fit(); });

  document.addEventListener('keydown', e => {
    if (!viewer.classList.contains('open')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(cur - 1);
    else if (e.key === 'ArrowRight') show(cur + 1);
    else if (e.key === '+' || e.key === '=') zoomCenter(1.5);
    else if (e.key === '-') zoomCenter(1 / 1.5);
    else if (e.key === 'Tab') { // keep focus inside the overlay
      const els = [...viewer.querySelectorAll('button,a[href]')].filter(el => !el.hidden);
      const a = els[0], z = els[els.length - 1];
      if (e.shiftKey && document.activeElement === a) { z.focus(); e.preventDefault(); }
      else if (!e.shiftKey && document.activeElement === z) { a.focus(); e.preventDefault(); }
    }
  });

  stage.addEventListener('wheel', e => {
    e.preventDefault();
    const r = stage.getBoundingClientRect();
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  }, { passive: false });
  stage.addEventListener('dblclick', e => {
    const r = stage.getBoundingClientRect(); zoomAt(2, e.clientX - r.left, e.clientY - r.top);
  });

  const pts = new Map();
  let pinch = null;
  stage.addEventListener('pointerdown', e => {
    stage.setPointerCapture(e.pointerId);
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    stage.classList.add('drag');
  });
  stage.addEventListener('pointermove', e => {
    const p = pts.get(e.pointerId); if (!p) return;
    const r = stage.getBoundingClientRect();
    if (pts.size === 1) { tx += e.clientX - p.x; ty += e.clientY - p.y; apply(); }
    p.x = e.clientX; p.y = e.clientY;
    if (pts.size === 2) {
      const [a, b] = [...pts.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y), mx = (a.x + b.x) / 2 - r.left, my = (a.y + b.y) / 2 - r.top;
      if (pinch) { tx += mx - pinch.mx; ty += my - pinch.my; apply(); zoomAt(d / pinch.d, mx, my); }
      pinch = { d, mx, my };
    }
  });
  const up = e => { pts.delete(e.pointerId); pinch = null; if (!pts.size) stage.classList.remove('drag'); };
  stage.addEventListener('pointerup', up);
  stage.addEventListener('pointercancel', up);

  chips.forEach(b => b.addEventListener('click', () => setVariant(b.dataset.variant)));
  let saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  if (saved === 'sw') setVariant('sw');
})();
