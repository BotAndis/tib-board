/* Static, local data; no account, writes, third-party scripts or remote image requests. */
"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const source = (url, label = "Quelle ↗") => /^(https:\/\/|#)/.test(url || "") ? `<a href="${esc(url)}">${esc(label)}</a>` : "";
const photo = (path, alt = "", extra = "") => /^img\/[a-z0-9-]+\.webp$/.test(path || "") ? `<img src="${path}" alt="${esc(alt)}" loading="lazy" ${extra}>` : "";
const collator = new Intl.Collator("de", {numeric:true,sensitivity:"base"});
let DATA;

function tasteMap() {
  const items = DATA.taste;
  let selected = items.findIndex(it => it.id === "kt-infrabel"), active = "alle";
  const labels = [["alle","Alle"],["liebt","liebt / eigene Arbeit"],["respektiert","respektiert"],["lehnt ab","lehnt ab"],["tib","TIB"]];
  const visible = it => active === "alle" || (active === "tib" ? it.kind === "tib" : it.urteil === active && it.kind !== "tib");
  $("taste-filters").innerHTML = labels.map(([id,label]) => `<button data-filter="${id}" aria-pressed="${id === active}">${label}</button>`).join("");
  $("taste-plane").insertAdjacentHTML("beforeend", items.map((it,i) => {
    const kind = it.kind === "tib" ? "study" : it.urteil === "lehnt ab" ? "reject" : it.urteil;
    const short = {boullee:"Boullée",labrouste:"Labrouste","mies-barcelona":"Mies · BCN","asplund-chapel":"Asplund",fehn:"Fehn","kahn-trenton":"Kahn",sonsbeek:"Sonsbeek",zumthor:"Zumthor",perret:"Perret",vannelle:"Van Nelle","r-ikone":"Branding","r-oneliner":"One-liner","r-ornament":"Dekor","r-faketektonik":"Pseudo-Tektonik","r-asymmetrie":"Effekt-Asymmetrie","r-funktion":"Programmform","r-holzhype":"Holz-Hype","r-neuesmuseum":"Collage"};
    const abbr = it.kind === "tib" ? it.id === "tib-bestand" ? "TIB" : it.id.slice(-1).toUpperCase() : short[it.id] || it.titel.slice(0,20);
    return `<button class="dot ${kind}" data-i="${i}" aria-label="${esc(it.titel + ' · ' + it.urteil)}" aria-pressed="false" title="${esc(it.titel + ' · ' + it.urteil + '\n' + it.beleg + '\n' + it.quelle)}">${photo(it.bild) || `<span class="abbr">${esc(abbr)}</span>`}</button>`;
  }).join(""));
  $("taste-list").innerHTML = items.map(it => `<article class="strategy"><div></div><div><h3>${esc(it.titel)}</h3><p><span class="tag">${esc(it.urteil)}</span> ${esc(it.scope)}</p><p>${esc(it.beleg)} ${source(it.quelle)}</p></div></article>`).join("");
  function show(i) {
    selected = i;
    const it = items[i];
    $("taste-plane").querySelectorAll(".dot").forEach(b => {
      b.classList.toggle("selected", +b.dataset.i === i);
      b.setAttribute("aria-pressed", String(+b.dataset.i === i));
    });
    $("taste-select").value = String(i);
    $("taste-detail").innerHTML = `${photo(it.bild,it.titel)}<p class="micro">${esc(it.scope)}</p><h3>${esc(it.titel)}</h3><p class="small mute">${esc([it.architekt,it.jahr].filter(Boolean).join(" · "))}</p><span class="tag">${esc(it.kind === "tib" ? "TIB · Studie / Vermutung" : it.urteil)}</span><p>${esc(it.beleg)}</p><p>${source(it.quelle, it.quelle === "#tib" ? "Entwurfsrichtung lesen ↓" : "Beleg lesen ↗")}</p>${it.bild_credit ? `<p class="small mute">Bild: ${esc(it.bild_credit)} · ${source(it.quelle,"Büro-Pressebild ↗")}</p>` : `<p class="small mute">Textkachel · ${source(it.quelle,"Projekt / Beleg ↗")}</p>`}<p class="small mute">Position: x ${it.x}, y ${it.y} · redaktionelle Einordnung (Vermutung).</p>`;
  }
  function layout() {
    const box = $("taste-plane"), w = box.clientWidth, h = box.clientHeight;
    const dots = [...box.querySelectorAll(".dot")].filter(b => !b.hidden);
    const size = dots[0]?.offsetWidth || 27, gap = size + 3, margin = size / 2 + 5;
    const points = dots.map(b => {
      const it = items[+b.dataset.i];
      const x = margin + (w - margin*2) * it.x / 100, y = margin + (h - margin*2) * (100-it.y) / 100;
      return {b,x,y,ox:x,oy:y};
    });
    // Screen-space decluttering only; source coordinates stay unchanged and are shown in the detail.
    for (let n=0;n<230;n++) {
      for (let i=0;i<points.length;i++) for (let j=i+1;j<points.length;j++) {
        const a=points[i],b=points[j];
        let dx=b.x-a.x,dy=b.y-a.y,dist=Math.hypot(dx,dy);
        if (dist<.01) { dx=(i%2 ? 1 : -1);dy=1;dist=Math.SQRT2; }
        if (dist<gap) { const move=(gap-dist)*.52/dist;a.x-=dx*move;a.y-=dy*move;b.x+=dx*move;b.y+=dy*move; }
      }
      for (const p of points) {
        p.x += (p.ox-p.x)*.015;p.y += (p.oy-p.y)*.015;
        p.x=Math.max(margin,Math.min(w-margin,p.x));p.y=Math.max(margin,Math.min(h-margin,p.y));
      }
    }
    points.forEach(p => {p.b.style.left=p.x+"px";p.b.style.top=p.y+"px";});
  }
  function filter() {
    $("taste-plane").querySelectorAll(".dot").forEach(b => b.hidden = !visible(items[+b.dataset.i]));
    $("taste-select").innerHTML = items.map((it,i) => visible(it) ? `<option value="${i}">${esc(it.titel)} · ${esc(it.urteil)}</option>` : "").join("");
    if (!visible(items[selected])) selected=items.findIndex(visible);
    show(selected);layout();
  }
  $("taste-filters").addEventListener("click", e => {
    const b=e.target.closest("button[data-filter]");if(!b)return;
    active=b.dataset.filter;
    [...b.parentElement.children].forEach(x=>x.setAttribute("aria-pressed",String(x===b)));
    filter();
  });
  $("taste-plane").querySelectorAll(".dot").forEach(b=>{
    b.addEventListener("click",()=>show(+b.dataset.i));
    b.addEventListener("pointerenter",e=>{if(e.pointerType==="mouse")show(+b.dataset.i);});
    b.addEventListener("focus",()=>show(+b.dataset.i));
  });
  $("taste-select").addEventListener("change",e=>show(+e.target.value));
  new ResizeObserver(layout).observe($("taste-plane"));
  filter();
}

function profile() {
  const fields=[
    ["Materialien","Große Glasscheiben, Sichtbeton und präzise eingesetzte Industrieprodukte.","https://tektoniek.nl/interview-andre-kempe/"],
    ["Fassaden","Ruhige Teilung; schlanke Profile; Wintergärten als räumlicher Mehrwert.","https://atelierkempethill.com/projects/0127-montmartre-housing/"],
    ["Struktur","Dauerhaftes Raster und großzügige Spannweiten für wechselnde Nutzungen.","https://tektoniek.nl/interview-andre-kempe/"],
    ["Raum","Atrium und Halle als kollektive Mitte; Leere lässt Aneignung zu.","https://atelierkempethill.com/projects/0282-centralesupelec-paris-saclay/"],
    ["Licht","Große Fenster, Oberlichter und Sheds; Licht prägt den gemeinsamen Raum.","https://atelierkempethill.com/projects/0206-infrabel-academy/"],
    ["Zeichnung","Feine Linien und viel Weiß; Flächen und Akzente gezielt, je nach Projekt.","https://atelierkempethill.com/projects/0099-university-library/"],
    ["Begriffe","Spezifische Neutralität · Typologie · Großzügigkeit · Kollektivraum.","https://atelierkempethill.com/office/"],
    ["Kritisierte Strategien","Branding · schneller formaler Einfall · nur vorgetäuschte Tektonik.","https://oasejournal.nl/wp-content/uploads/2025/05/OASE-67-56-Nieuwe-Discipline.pdf"]
  ];
  $("steckbrief").innerHTML=fields.map(([title,text,url])=>`<article><h3>${title}</h3><p>${esc(text)} ${source(url)}</p></article>`).join("");
}

function projectAtlas() {
  const P=DATA.projects,groups=[...new Set(P.map(p=>p.gruppe))];
  const state={group:"",q:"",sort:"titel",dir:1,all:false,selected:""};
  $("project-groups").innerHTML=[["","Alle Gruppen"],...groups.map(g=>[g,g])].map(([g,label])=>`<button data-group="${esc(g)}" aria-pressed="${!g}">${esc(label)}</button>`).join("");
  let mobileMap;
  function drawMindMap() {
    mobileMap=matchMedia("(max-width:760px)").matches;
    let svg=`<svg class="mindmap" viewBox="0 0 ${mobileMap?"400 790":"1000 450"}" role="group" aria-label="Projektmindmap: Atelier Kempe Thill und neun Projektgruppen">`;
    groups.forEach((g,i)=>{
      const left=i<5,x=mobileMap?60:left?12:688,y=mobileMap?110+i*75:20+(left?i:i-5)*83;
      const edge=mobileMap?`M200 73 H36 V${y+28} H60`:`M${left?400:600} 224 C${left?350:650} 224 ${left?350:650} ${y+28} ${left?312:688} ${y+28}`;
      svg+=`<path d="${edge}" fill="none" stroke="#e7e7e7"/><g class="branch" tabindex="0" role="button" aria-pressed="${state.group===g}" aria-label="${esc(g)} filtern" data-group="${esc(g)}"><rect x="${x}" y="${y}" width="${mobileMap?326:300}" height="57" rx="2" fill="#fff" stroke="#e7e7e7"/><text x="${x+14}" y="${y+23}">${esc(g)}</text><text class="count" x="${x+14}" y="${y+43}">${P.filter(p=>p.gruppe===g).length} Projekte · öffnen</text></g>`;
    });
    const rx=mobileMap?24:400,ry=mobileMap?16:196,rw=mobileMap?352:200,cx=rx+rw/2;
    svg+=`<rect x="${rx}" y="${ry}" width="${rw}" height="57" fill="#1a1a1a"/><text x="${cx}" y="${ry+24}" text-anchor="middle" style="fill:white">Atelier Kempe Thill</text><text x="${cx}" y="${ry+43}" text-anchor="middle" style="fill:white;font-size:11px">142 Einträge · 9 Gruppen</text></svg>`;
    $("mindmap").innerHTML=svg;
  }
  drawMindMap();
  addEventListener("resize",()=>{if(mobileMap!==matchMedia("(max-width:760px)").matches)drawMindMap();});
  function render() {
    let rows=P.filter(p=>(!state.group||p.gruppe===state.group)&&(!state.q||[p.titel,p.ort,p.partner,p.typologie,p.eingriff,p.status,p.idee,...p.themen].join(" ").toLocaleLowerCase("de").includes(state.q)));
    const key=state.sort==="jahr"?"jahr_sort":state.sort;
    rows.sort((a,b)=>{
      const x=a[key],y=b[key],empty=v=>v==null||v===""||v==="unbekannt";
      if(empty(x)!==empty(y))return empty(x)?1:-1;
      return (typeof x==="number"&&typeof y==="number"?x-y:collator.compare(String(x??""),String(y??"")))*state.dir||collator.compare(a.slug,b.slug);
    });
    $("project-count").textContent=`${rows.length} von ${P.length} Projekten${state.group?" · "+state.group:""}${state.all||state.group||state.q?"":" · zunächst 30 sichtbar"}`;
    const shown=state.all||state.group||state.q?rows:rows.slice(0,30);
    $("project-table").querySelector("tbody").innerHTML=shown.map(p=>`<tr data-slug="${esc(p.slug)}" class="${p.slug===state.selected?"selected":""}"><td>${source(p.url||p.quellen[0],p.titel_kurz||p.titel)||esc(p.titel_kurz||p.titel)}<div class="row-meta">${esc(p.nr)}${p.partner?" · "+esc(p.partner):""}</div></td><td>${esc(p.ort)}<div class="row-meta">${esc(p.land)}</div></td><td title="${esc(p.jahr)}">${esc(p.jahr_kurz||p.jahr||"unbekannt")}</td><td>${esc(p.typologie)}<div class="row-meta">${esc(p.eingriff)}</div></td><td class="status">${esc(p.status||"unbekannt")}</td><td>${esc(p.idee)} ${source(p.quellen[0])}</td></tr>`).join("") || '<tr><td colspan="6">Keine Projekte gefunden.</td></tr>';
    $("all-projects").hidden=state.all||!!state.group||!!state.q||rows.length<=30;
    $("project-table").querySelectorAll("th[data-active],th[aria-sort]").forEach(th=>{th.removeAttribute("aria-sort");th.removeAttribute("data-active");});
    $("project-table").querySelectorAll("button[data-sort]").forEach(b=>{
      const label={titel:"Projekt",ort:"Ort",jahr:"Jahr",gruppe:"Typ / Eingriff",status:"Status"}[b.dataset.sort];
      const selected=b.dataset.sort===state.sort;b.textContent=label+(selected?(state.dir>0?" ↑":" ↓"):"");
      if(selected)b.parentElement.setAttribute("aria-sort",state.dir>0?"ascending":"descending");
    });
  }
  function group(g) {
    state.group=g;state.selected="";$("project-detail").hidden=true;
    document.querySelectorAll("#project-groups [data-group],#mindmap [data-group]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.group===g)));
    $("map-projects").innerHTML=g?P.filter(p=>p.gruppe===g).map(p=>`<button data-project="${esc(p.slug)}" aria-pressed="false">${esc(p.titel_kurz||p.titel)}</button>`).join(""):"";
    render();
  }
  function openProject(slug) {
    const p=P.find(p=>p.slug===slug);state.selected=slug;
    $("project-detail").hidden=false;
    $("project-detail").innerHTML=`${photo(p.bild,p.titel,'style="max-width:260px"')}<p class="micro">${esc(p.gruppe)}</p><h3>${esc(p.titel)}</h3><p>${esc(p.ort)} · ${esc(p.jahr)} · ${esc(p.status)}</p><p>${esc(p.idee)}</p><p>${p.themen.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</p><p>${p.quellen.map(u=>source(u)).join(" · ")}</p>${p.bild_credit?`<p class="small mute">Bild: ${esc(p.bild_credit)} · ${source(p.url,"Büro-Pressebild ↗")}</p>`:""}`;
    $("map-projects").querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.project===slug)));
    render();
  }
  $("project-groups").addEventListener("click",e=>{const b=e.target.closest("[data-group]");if(b)group(b.dataset.group);});
  $("mindmap").addEventListener("click",e=>{const b=e.target.closest("[data-group]");if(b)group(b.dataset.group);});
  $("mindmap").addEventListener("keydown",e=>{const b=e.target.closest("[data-group]");if(b&&["Enter"," "].includes(e.key)){e.preventDefault();group(b.dataset.group);}});
  $("map-projects").addEventListener("click",e=>{const b=e.target.closest("[data-project]");if(b)openProject(b.dataset.project);});
  $("project-search").addEventListener("input",e=>{state.q=e.target.value.trim().toLocaleLowerCase("de");render();});
  $("project-table").querySelector("thead").addEventListener("click",e=>{
    const b=e.target.closest("button[data-sort]");if(!b)return;
    const key=b.dataset.sort;state.dir=state.sort===key?-state.dir:1;state.sort=key;render();
  });
  $("all-projects").addEventListener("click",()=>{state.all=true;render();});
  group("");
}

function references() {
  $("reference-grid").innerHTML=DATA.references.map(r=>{
    const url=r.library?`../referenzen/index.html?filter=kt#${r.slug}`:r.source;
    return `<article>${r.image?photo(r.image,r.title):`<a class="text-tile" href="${esc(url)}"><span>${r.library?"Bibliothek · Grundrisse im Vergleich":"Projektquelle"}</span><b>${esc(r.title)}</b><span>${esc(r.place)} · ${esc(r.year)} ↗</span></a>`}${r.credit?`<p class="credit">Bild: ${esc(r.credit)} · ${source(r.source,"Büro-Pressebild ↗")}</p>`:""}<h3><a href="${esc(url)}">${esc(r.title)}</a></h3><p class="mute">${esc(r.architect)} · ${esc(r.place)} · ${esc(r.year)}</p><p><b>${esc(r.theme)}.</b> ${esc(r.lesson)} ${source(r.source)}</p><p class="small mute">${esc(r.fit)}</p></article>`;
  }).join("");
}

function sources() {
  const urls=new Map();
  const collect=(url,label)=>{if(/^https:\/\//.test(url||""))urls.set(url,urls.get(url)||label);};
  document.querySelectorAll('main a[href^="https://"]').forEach(a=>collect(a.href,a.textContent.replace(/ ↗$/, "")));
  DATA.projects.forEach(p=>{collect(p.url,p.titel);p.quellen.forEach(u=>collect(u,p.titel));});
  DATA.taste.forEach(t=>collect(t.quelle,t.titel));DATA.references.forEach(r=>collect(r.source,r.title));
  $("source-count").textContent=`${urls.size} verwendete Quellen anzeigen`;
  $("source-list").innerHTML=[...urls].sort((a,b)=>collator.compare(a[0],b[0])).map(([url,label])=>`<li>${source(url,label)}<span>${esc(url)}</span></li>`).join("");
  $("image-credits").innerHTML=DATA.assets.map(a=>`<li><a href="img/${esc(a.file)}">${esc(a.file)}</a><span>${esc(a.credit)} · ${a.size.join(" × ")} px · Büro-Pressebild</span>${source(a.url,"Originaldatei ↗")} · ${source(DATA.projects.find(p=>p.slug===a.slug)?.url,"Projekt ↗")}</li>`).join("")+`<li><a href="img/fribourg-grundrisse.webp">fribourg-grundrisse.webp</a><span>Plan: Atelier Kempe Thill · Büro-Pressebild · verkleinert</span>${source("https://atelierkempethill.com/projects/0099-university-library/","Projekt und Planquelle ↗")}</li>`;
}

fetch("data.json").then(response=>{if(!response.ok)throw new Error("Projektdaten konnten nicht geladen werden.");return response.json();}).then(data=>{
  DATA=data;tasteMap();profile();projectAtlas();references();sources();
  if(location.hash)document.getElementById(location.hash.slice(1))?.scrollIntoView();
}).catch(error=>{$("load-error").hidden=false;$("load-error").textContent=error.message;});
