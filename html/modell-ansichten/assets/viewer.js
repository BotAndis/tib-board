// Shared review viewer: synced pan/zoom SVG sheets, layer controls (on/off + opacity), swipe. Data: js/*.js (window.TIB).
const V = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };
  const h = (tag, attrs, parent, html) => {
    const e = document.createElement(tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  };

  // One View = one shared viewBox for every attached svg, so panes and stacked sheets stay in sync.
  class View {
    constructor(box) { this.home = box.slice(); this.box = box.slice(); this.svgs = []; this.pointers = new Map(); this.pinch = null; }
    apply() { const b = this.box.join(" "); this.svgs.forEach(s => s.setAttribute("viewBox", b)); }
    reset() { this.box = this.home.slice(); this.apply(); }
    zoomTo(cx, cy, w, hgt) { this.box = [cx - w / 2, cy - hgt / 2, w, hgt]; this.apply(); }
    attach(svg) {
      this.svgs.push(svg); svg.setAttribute("viewBox", this.box.join(" "));
      let drag = null;
      const scale = () => Math.max(this.box[2] / svg.clientWidth, this.box[3] / svg.clientHeight);
      const point = (x, y) => {
        const p = svg.createSVGPoint(); p.x = x; p.y = y;
        return p.matrixTransform(svg.getScreenCTM().inverse());
      };
      const gesture = () => {
        const [a, b] = [...this.pointers.values()];
        return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, d: Math.hypot(a.x - b.x, a.y - b.y) };
      };
      svg.addEventListener("wheel", e => {
        if (!e.ctrlKey && !e.metaKey) return;
        e.preventDefault();
        const q = point(e.clientX, e.clientY), k = e.deltaY > 0 ? 1.18 : 1 / 1.18, b = this.box;
        this.box = [q.x - (q.x - b[0]) * k, q.y - (q.y - b[1]) * k, b[2] * k, b[3] * k]; this.apply();
      }, { passive: false });
      svg.addEventListener("pointerdown", e => {
        if (e.pointerType === "mouse" && e.button === 0) {
          drag = { id: e.pointerId, x: e.clientX, y: e.clientY, b: this.box.slice(), s: scale() };
          svg.setPointerCapture(e.pointerId);
        } else if (e.pointerType === "touch") {
          this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
          svg.setPointerCapture(e.pointerId);
          if (this.pointers.size === 2) this.pinch = gesture();
        }
      });
      svg.addEventListener("pointermove", e => {
        if (this.pointers.has(e.pointerId)) {
          this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
          if (this.pointers.size !== 2 || !this.pinch) return;
          const p = this.pinch, next = gesture(); this.pinch = next;
          if (!p.d || !next.d) return;
          e.preventDefault();
          const q = point(p.x, p.y), r = point(next.x, next.y), k = p.d / next.d, b = this.box;
          this.box = [q.x - (r.x - b[0]) * k, q.y - (r.y - b[1]) * k, b[2] * k, b[3] * k]; this.apply();
        } else if (drag && drag.id === e.pointerId) {
          this.box = [drag.b[0] - (e.clientX - drag.x) * drag.s, drag.b[1] - (e.clientY - drag.y) * drag.s, drag.b[2], drag.b[3]]; this.apply();
        }
      });
      const end = e => {
        if (drag?.id === e.pointerId) drag = null;
        this.pointers.delete(e.pointerId);
        this.pinch = this.pointers.size === 2 ? gesture() : null;
      };
      ["pointerup", "pointercancel", "lostpointercapture"].forEach(type => svg.addEventListener(type, end));
      svg.addEventListener("dblclick", () => this.reset());
    }
  }

  // pane with n stacked sheets (sheet 0 at the bottom)
  function pane(parent, caption, view, n = 1) {
    const div = h("div", { class: "pane" }, parent);
    if (caption) h("div", { class: "cap" }, div, caption);
    const sheets = [];
    for (let i = 0; i < n; i++) { const s = svgEl("svg", { preserveAspectRatio: "xMidYMid meet" }, div); view.attach(s); sheets.push(s); }
    return { div, sheets };
  }

  // ---- layers: every <g class="L-id"> follows the shared state of that id ----
  const state = {};
  const layer = (svg, id) => svgEl("g", { class: "L-" + id }, svg);
  function applyLayer(id) {
    const s = state[id]; if (!s) return;
    document.querySelectorAll(".L-" + id).forEach(g => { g.style.display = s.on ? "" : "none"; g.style.opacity = s.op; });
  }
  const applyAll = () => Object.keys(state).forEach(applyLayer);
  function controls(parent, defs) {
    defs.forEach(d => {
      if (!state[d.id]) state[d.id] = { on: d.on !== false, op: d.op ?? 1 };
      const s = state[d.id], row = h("label", { class: "ctl" }, parent);
      const cb = h("input", { type: "checkbox" }, row); cb.checked = s.on;
      h("span", {}, row, `<span class="sw" style="background:${d.color || "#999"}"></span> ${d.label}`);
      const r = h("input", { type: "range", min: 0, max: 100 }, row); r.value = Math.round(s.op * 100);
      cb.onchange = () => { s.on = cb.checked; applyLayer(d.id); };
      r.oninput = () => { s.op = r.value / 100; applyLayer(d.id); };
    });
    applyAll();
  }

  // all paths of one style in one <path> (fast for thousands of polylines); stroke width stays in screen px
  function paths(g, list, stroke, w = 1, fill = "none") {
    if (!list || !list.length) return;
    svgEl("path", { d: list.join(" "), stroke: stroke || "none", "stroke-width": w, fill, "fill-rule": "evenodd",
      "vector-effect": "non-scaling-stroke", "stroke-linejoin": "round", "stroke-linecap": "round" }, g);
  }
  const img = (g, href, x, y, w, hgt, cls) => svgEl("image", { href, x, y, width: w, height: hgt, preserveAspectRatio: "none", class: cls || "" }, g);

  // swipe: hides the top sheet left of the slider position
  function swipe(parent, p, label) {
    const line = h("div", { class: "swipe" }, p.div); line.style.left = "0%";
    const row = h("div", { class: "ctl" }, parent);
    h("span", {}, row, ""); h("span", {}, row, label);
    const r = h("input", { type: "range", min: 0, max: 100, value: 0 }, row);
    const top = p.sheets[p.sheets.length - 1];
    r.oninput = () => { top.style.clipPath = `inset(0 0 0 ${r.value}%)`; line.style.left = r.value + "%"; };
  }

  function buttons(parent, label, items, cur, onPick) {
    const bar = h("div", { class: "bar" }, parent);
    if (label) h("span", { class: "lab" }, bar, label);
    items.forEach(([k, txt]) => {
      const b = h("button", { type: "button", class: "t" + (k === cur ? " on" : ""), "aria-pressed": k === cur }, bar, txt);
      b.onclick = () => {
        bar.querySelectorAll("button").forEach(x => { x.classList.remove("on"); x.setAttribute("aria-pressed", "false"); });
        b.classList.add("on"); b.setAttribute("aria-pressed", "true"); onPick(k);
      };
    });
    return bar;
  }

  function lightbox() {
    const lb = h("div", { id: "lightbox" }, document.body), im = h("img", {}, lb);
    lb.onclick = () => { lb.style.display = "none"; };
    document.addEventListener("click", e => {
      if (e.target.matches("img.zoomable")) { im.src = e.target.src; lb.style.display = "flex"; }
    });
  }

  return { svgEl, h, View, pane, layer, controls, applyAll, paths, img, swipe, buttons, lightbox, state };
})();
