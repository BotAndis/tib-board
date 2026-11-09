const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let projects = [], assets = [], filter = 'alle', currentImages = [], currentIndex = 0;
const kindName = {photo:'Projektfoto', section:'Schnitt', plan:'Grundriss', axon:'Axonometrie'};
const imagesFor = id => assets.filter(image => image.project === id);
const imageCredit = image => image.credit;

function figure(image, project) {
  return `<figure class="${esc(image.kind)}"><button type="button" data-project="${esc(project.id)}" data-file="${esc(image.file)}" aria-label="${esc(project.title)}: ${esc(image.caption)} vergrößern"><img src="${esc(image.file)}" alt="${esc(image.caption)}" loading="lazy" decoding="async" width="1400" height="950"></button><figcaption><strong>${esc(kindName[image.kind] || 'Zeichnung')} · </strong>${esc(image.caption)}<span class="credit">${esc(imageCredit(image))} · <a href="${esc(image.source)}" target="_blank" rel="noopener">Quelle ↗</a>${image.license ? ` · <a href="${esc(image.license)}" target="_blank" rel="noopener">Lizenz</a>` : ''}</span></figcaption></figure>`;
}

function render() {
  const shown = projects.filter(p => filter === 'alle' || p.tags.includes(filter));
  $('count').textContent = `${shown.length} von ${projects.length} Projekten`;
  $('overview').innerHTML = shown.map(p => {
    const image = imagesFor(p.id).find(i => i.kind === 'photo') || imagesFor(p.id)[0];
    return `<a href="#${esc(p.id)}" aria-label="${esc(p.title)} · ${esc(p.place)}"><figure>${image ? `<img src="${esc(image.file)}" alt="${esc(p.title)}" loading="lazy" width="480" height="300">` : ''}<figcaption><strong>${esc(p.title)}</strong><small>${esc(p.place)} · ${esc(p.year)}</small></figcaption></figure></a>`;
  }).join('');
  $('projects').innerHTML = shown.map(p => {
    const index = projects.findIndex(item => item.id === p.id);
    return `<article class="project" id="${esc(p.id)}"><header class="project-head"><span class="number" aria-hidden="true">${String(index + 1).padStart(2,'0')}</span><div><h2>${esc(p.title)}</h2><p class="meta">${esc(p.architect)} · ${esc(p.place)} · ${esc(p.year)}</p><span class="type">${esc(p.type)}</span><a class="project-report" href="${esc(p.report.url)}" target="_blank" rel="noopener">Projektbericht · ${esc(p.report.label)} ↗</a><p class="principle">${esc(p.principle)}</p></div></header><div class="gallery">${imagesFor(p.id).map(image => figure(image,p)).join('')}</div><p class="reading"><strong>Im Bild lesen</strong>${esc(p.look)}</p><div class="analysis"><div><h3>So funktioniert es</h3><p>${esc(p.mechanism)}</p></div><div><h3>Was gut funktioniert</h3><ul>${p.strengths.map(text => `<li>${esc(text)}</li>`).join('')}</ul></div><div><h3>Grenzen und Nachteile</h3><ul>${p.limits.map(text => `<li>${esc(text)}</li>`).join('')}</ul></div></div><div class="tib"><h3>Für die TIB</h3><div><p>${esc(p.tib)}</p><p class="assessment">${esc(p.assessment)}</p></div></div><div class="sources">${p.sources.map(source => `<a class="source" href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)} ↗</a>`).join('')}</div></article>`;
  }).join('');
}

function showImage() {
  const image = currentImages[currentIndex];
  const project = projects.find(p => p.id === image.project);
  $('lb-image').src = image.file;
  $('lb-image').alt = image.caption;
  $('lb-title').textContent = `${project.title} · ${currentIndex + 1}/${currentImages.length}`;
  $('lb-caption').textContent = `${image.caption} · ${imageCredit(image)}`;
  $('lb-source').href = image.source;
  $('lb-original').href = image.file;
  $('lb-prev').disabled = currentImages.length < 2;
  $('lb-next').disabled = currentImages.length < 2;
}

document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  render();
}));
$('projects').addEventListener('click', event => {
  const button = event.target.closest('[data-file]');
  if (!button) return;
  currentImages = imagesFor(button.dataset.project);
  currentIndex = currentImages.findIndex(image => image.file === button.dataset.file);
  showImage();
  $('lightbox').showModal();
});
function stepImage(direction) {
  currentIndex = (currentIndex + direction + currentImages.length) % currentImages.length;
  showImage();
}
$('lb-close').addEventListener('click', () => $('lightbox').close());
$('lb-prev').addEventListener('click', () => stepImage(-1));
$('lb-next').addEventListener('click', () => stepImage(1));
$('lightbox').addEventListener('keydown', event => {
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault();
    stepImage(event.key === 'ArrowLeft' ? -1 : 1);
  }
});
// A comparison link also reveals a project hidden by the active filter.
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || filter === 'alle') return;
  const id = link.getAttribute('href').slice(1);
  const project = projects.find(p => p.id === id);
  if (project && !project.tags.includes(filter)) document.querySelector('[data-filter="alle"]').click();
});

Promise.all(['data.json','assets.json'].map(async path => {
  const response = await fetch(path);
  if (!response.ok) throw new Error(path);
  return response.json();
})).then(([projectData,imageData]) => {
  projects = projectData;
  assets = imageData;
  render();
  if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView();
}).catch(() => {
  $('projects').innerHTML = '<p class="load-error">Die Projekte konnten nicht geladen werden. Bitte die Seite erneut laden.</p>';
});
