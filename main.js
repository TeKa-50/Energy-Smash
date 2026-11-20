/* main.js: renderizado de las secciones, ficha de producto, eventos y arranque */

const PAGINA = 12;   // tarjetas que se muestran por tanda en el catálogo
const filtro = { perfil: 'todos', marca: null, q: '', n: PAGINA };
const toast = msg => { const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; $('#toasts').append(t); setTimeout(() => t.remove(), 3000); };
const abrirCarrito = () => { pintar(); $('#cartDrawer').showModal(); };

/* ---------- Tarjeta de producto reutilizable ---------- */
function card(p, { flash, puesto } = {}) {
  const c = p.colores[0], o = p.oferta, id = esc(p.id);
  return `<article class="card">${puesto ? `<b class="rank">${puesto}</b>` : ''}${o ? `<span class="chip">−${o.descuento}%</span>` : ''}
    <button class="media" data-a="ver" data-id="${id}" aria-label="Ver ${esc(p.nombre)}"><img src="${imagenes(p, c.id)[0]}" alt="${esc(p.nombre)} en ${esc(c.nombre)}" loading="lazy"></button>
    <div class="body"><p class="brand">${esc(marca(p.marca))}</p><h3>${esc(p.nombre)}</h3>${p.rating ? `<p class="rate">★ ${p.rating.toFixed(1)} (${p.ventas} vendidos)</p>` : ''}
      <p class="price">${money(precio(p, p.capacidades[0].id))}${o ? ` <s>${money(p.precioBase)}</s>` : ''}</p>
      ${flash && o ? `<div class="stock" title="${o.vendido}% vendido"><span style="width:${o.vendido}%"></span></div><small class="muted">${o.vendido}% vendido</small>` : ''}</div>
    <div class="acts"><button class="btn ghost sm" data-a="ver" data-id="${id}">Detalles</button><button class="btn sm" data-a="add" data-id="${id}">Añadir</button></div></article>`;
}

/* ---------- Secciones ---------- */
function pintarMarcas() {
  $('#brands').innerHTML = DATA.marcas.map(m => `<button class="brand-tile${filtro.marca === m.id ? ' on' : ''}" data-a="marca" data-id="${esc(m.id)}" aria-pressed="${filtro.marca === m.id}">
    ${esc(m.nombre)}<small>${DATA.productos.filter(p => p.marca === m.id).length} modelos</small></button>`).join('');
}
function pintarCatalogo() {
  $('#tabs').innerHTML = [{ id: 'todos', nombre: 'Todos' }, ...DATA.perfiles].map(t =>
    `<button class="tab" data-a="perfil" data-id="${esc(t.id)}" aria-pressed="${filtro.perfil === t.id}">${esc(t.nombre)}</button>`).join('');
  const q = norm(filtro.q);
  const lista = DATA.productos.filter(p => (filtro.perfil === 'todos' || p.perfiles.includes(filtro.perfil)) && (!filtro.marca || p.marca === filtro.marca)
    && (!q || norm(`${p.nombre} ${marca(p.marca)} ${p.descripcion}`).includes(q)));
  const vis = lista.slice(0, filtro.n);
  $('#catGrid').innerHTML = lista.length ? vis.map(p => card(p)).join('')
    : '<p class="empty">Ningún smartphone coincide con estos filtros. <button class="link" data-a="reset">Quitar filtros</button></p>';
  $('#catMore').innerHTML = !lista.length ? '' : `<p class="muted">Mostrando ${vis.length} de ${lista.length} smartphones</p>${vis.length < lista.length ? '<button class="btn ghost" data-a="mas">Mostrar más</button>' : ''}`;
}
function pintarTodo() {
  const P = DATA.productos, n = P.find(p => p.nuevo) || P[0], img = n && imagenes(n, n.colores[0].id);
  if (!n) $('#hero').innerHTML = '<p class="empty">El catálogo está vacío. Ejecuta <code>python scripts/integrar_catalogo.py</code> para cargar celulares reales con sus fotos.</p>';
  else $('#hero').innerHTML = `<div><p class="challenger">¡Nuevo desafiante!</p><h1>${esc(n.nombre)}</h1><p class="lead">${esc(n.descripcion)}</p>
    <ul class="chips">${n.specs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>
    <div class="hero-buy"><p class="price"><small>Desde</small> ${money(precio(n, n.capacidades[0].id))}</p><button class="btn lg" data-a="ver" data-id="${esc(n.id)}">Comprar ahora</button></div></div>
    <div class="hero-visual" aria-hidden="true"><span class="word">SMASH</span><img class="ph-b" src="${img[1] ?? img[0]}" alt=""><img class="ph-a" src="${img[0]}" alt=""></div>`;
  $('#totalModelos').textContent = `${P.length} modelos de ${DATA.marcas.length} marcas`;
  pintarMarcas();
  $('#flashGrid').innerHTML = P.filter(p => p.oferta).map(p => card(p, { flash: 1 })).join('');
  $('#favGrid').innerHTML = [...P].sort((a, b) => (b.ventas || 0) - (a.ventas || 0)).slice(0, 4).map((p, i) => card(p, { puesto: i + 1 })).join('');
  pintarCatalogo();
  $('#accGrid').innerHTML = DATA.accesorios.map(a => `<article class="acc"><span class="ico">${a.icono}</span><h3>${esc(a.nombre)}</h3>
    <p class="muted">${esc(a.categoria)}</p><p class="price">${money(a.precio)}</p><button class="btn ghost sm" data-a="acc" data-id="${esc(a.id)}">Añadir</button></article>`).join('');
  $('#guideGrid').innerHTML = DATA.guias.map(g => `<article class="guide ${esc(g.acento)}"><div class="gv">${g.icono}</div>
    <div><h3>${esc(g.titulo)}</h3><p class="muted">${esc(g.tiempo)} de lectura</p><button class="link" data-a="guia">Leer guía</button></div></article>`).join('');
}

/* ---------- Ficha de producto: color, almacenamiento y galería en tiempo real ---------- */
let sel;
function ficha(id) {
  const p = prod(id); sel = { p, color: p.colores[0].id, cap: p.capacidades[0].id, i: 0 };
  $('#productDialog').innerHTML = `<div class="inner ficha"><button class="x" data-close aria-label="Cerrar">✕</button>
    <div><img id="fMain" class="fmain" alt=""><div id="fThumbs" class="thumbs"></div></div>
    <div class="finfo"><p class="brand">${esc(marca(p.marca))}</p><h2>${esc(p.nombre)}</h2><p class="muted">${esc(p.descripcion)}</p>
      <p class="price"><span id="fPrice"></span>${p.oferta ? ` <s>${money(p.precioBase)}</s>` : ''}</p>
      <p class="lbl">Color: <span id="fColor"></span></p>
      <div class="opts">${p.colores.map(c => `<button class="sw" data-color="${esc(c.id)}" style="background:${esc(c.hex)}" aria-label="${esc(c.nombre)}"></button>`).join('')}</div>
      <p class="lbl">Almacenamiento</p>
      <div class="opts">${p.capacidades.map(c => `<button class="opt" data-cap="${esc(c.id)}">${esc(c.id)}</button>`).join('')}</div>
      <ul class="chips">${p.specs.map(s => `<li>${esc(s)}</li>`).join('')}</ul>
      <button class="btn lg block" data-ficha-add>Añadir al carrito</button></div></div>`;
  fichaAct(); $('#productDialog').showModal();
}
function fichaAct() {
  const { p, color, cap, i } = sel, c = p.colores.find(x => x.id === color), imgs = imagenes(p, color), m = $('#fMain');
  m.src = imgs[i]; m.alt = `${p.nombre} en ${c.nombre}`; m.classList.remove('pop'); void m.offsetWidth; m.classList.add('pop');
  $('#fThumbs').innerHTML = imgs.map((s, k) => `<button class="th${k === i ? ' on' : ''}" data-i="${k}" aria-label="Vista ${k + 1}"><img src="${s}" alt=""></button>`).join('');
  $('#fColor').textContent = c.nombre; $('#fPrice').textContent = money(precio(p, cap));
  $$('[data-color]').forEach(b => b.classList.toggle('on', b.dataset.color === color));
  $$('[data-cap]').forEach(b => b.classList.toggle('on', b.dataset.cap === cap));
}

/* ---------- Eventos (delegación: un solo listener para toda la página) ---------- */
const acciones = {
  ver: id => ficha(id),
  add: id => { const p = prod(id); agregar('tel', id, p.colores[0].id, p.capacidades[0].id); toast(`${p.nombre} añadido al carrito.`); },
  acc: id => { agregar('acc', id); toast('Accesorio añadido al carrito.'); },
  marca: id => { filtro.marca = filtro.marca === id ? null : id; filtro.n = PAGINA; pintarMarcas(); pintarCatalogo(); $('#catalogo').scrollIntoView(); },
  perfil: id => { filtro.perfil = id; filtro.n = PAGINA; pintarCatalogo(); },
  mas: () => { filtro.n += PAGINA; pintarCatalogo(); },
  reset: () => { Object.assign(filtro, { perfil: 'todos', marca: null, q: '', n: PAGINA }); $('#q').value = ''; pintarMarcas(); pintarCatalogo(); },
  carrito: abrirCarrito, login: abrirAuth, guia: () => toast('Esta guía estará disponible muy pronto.'),
};
document.addEventListener('click', e => {
  const t = e.target;
  if (t.closest('[data-close]')) return t.closest('dialog').close();
  if (t instanceof HTMLDialogElement) return t.close();                       // clic en el fondo oscuro
  const a = t.closest('[data-a]'); if (a) return acciones[a.dataset.a]?.(a.dataset.id);
  const f = t.closest('[data-color],[data-cap],[data-i],[data-ficha-add]'); if (!f) return;
  if (f.dataset.color) { sel.color = f.dataset.color; sel.i = 0; }
  else if (f.dataset.cap) sel.cap = f.dataset.cap;
  else if (f.dataset.i) sel.i = +f.dataset.i;
  else { agregar('tel', sel.p.id, sel.color, sel.cap); $('#productDialog').close(); return abrirCarrito(); }
  fichaAct();
});
$('#searchForm').addEventListener('submit', e => { e.preventDefault(); filtro.q = $('#q').value; filtro.n = PAGINA; pintarCatalogo(); $('#catalogo').scrollIntoView(); });
$('#q').addEventListener('input', e => { filtro.q = e.target.value; filtro.n = PAGINA; pintarCatalogo(); });
$('#news').addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target, msg = $('#newsMsg'), btn = f.querySelector('button');
  const mostrar = (txt, mal) => { msg.textContent = txt; msg.className = 'news-msg' + (mal ? ' bad' : ''); };
  if (!f.consent.checked) return mostrar('Marca la casilla para aceptar el aviso de privacidad.', 1);
  btn.disabled = true; mostrar('Enviando…');
  try {
    const r = await fetch(API_BASE + '/api/suscribir', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: f.email.value, consentimiento: true }) });
    const d = await r.json();
    mostrar(d.mensaje, !r.ok); if (r.ok) f.reset();
  } catch { mostrar('No pudimos conectar con el servidor de correo. Inicia la tienda con: python server/servidor.py', 1); }
  btn.disabled = false;
});
$('#year').textContent = new Date().getFullYear();

/* ---------- Temporizador de ofertas flash (ciclos de 6 h guardados en LocalStorage) ---------- */
function reloj() {
  let fin = local.get('flashFin', 0);
  if (fin < Date.now()) { fin = Date.now() + 6 * 36e5; local.set('flashFin', fin); }
  const s = Math.max(0, Math.floor((fin - Date.now()) / 1e3)), v = { h: s / 3600 | 0, m: s % 3600 / 60 | 0, s: s % 60 };
  for (const u in v) $('#cd-' + u).textContent = String(v[u]).padStart(2, '0');
}
reloj(); setInterval(reloj, 1000);

/* ---------- Arranque ---------- */
initAuth();
loadCatalog().then(() => {
  pintarTodo();
  initCart(t => {                                                              // "Finalizar compra" simulado
    if (!usuario()) { $('#cartDrawer').close(); toast('Inicia sesión para completar tu compra.'); return abrirAuth(); }
    const folio = 'ES-' + Date.now().toString(36).toUpperCase().slice(-6) + Math.random().toString(36).slice(2, 4).toUpperCase();
    local.set('pedidos', [{ folio, fecha: new Date().toISOString(), email: usuario().email, total: t.total,
      lineas: t.lineas.map(l => ({ nombre: l.nombre, det: l.det, precio: l.precio, qty: l.qty })) }, ...local.get('pedidos', [])]);
    vaciar(); $('#cartDrawer').close(); toast(`¡Pedido simulado confirmado, ${usuario().nombre}! Folio ${folio}. Total: ${money(t.total)}.`);
  });
}).catch(() => { $('#hero').innerHTML = '<p class="empty">No se pudo cargar el catálogo. Revisa que productos.json y la carpeta js/ estén junto a index.html.</p>'; });
