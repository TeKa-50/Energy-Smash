/* cart.js: carrito persistente, totales en tiempo real y cupones */

let items = local.get('carrito', []);   // [{key, t:'tel'|'acc', id, color, cap, qty}]
let cupon = local.get('cupon', null);   // código aplicado
const guardar = () => { local.set('carrito', items); local.set('cupon', cupon); };

/* Convierte un ítem guardado en una línea con datos actuales del catálogo */
function linea(i) {
  if (i.t === 'acc') { const a = acc(i.id); return a && { ...i, nombre: a.nombre, det: a.categoria, precio: a.precio, ico: a.icono }; }
  const p = prod(i.id); if (!p) return null;
  const c = p.colores.find(x => x.id === i.color) || p.colores[0];
  return { ...i, nombre: p.nombre, det: `${c.nombre}, ${i.cap}`, precio: precio(p, i.cap), img: imagenes(p, c.id)[0] };
}

function totales() {
  const lineas = items.map(linea).filter(Boolean);
  const sub = lineas.reduce((s, l) => s + l.precio * l.qty, 0);
  const c = DATA.cupones.find(x => x.codigo === cupon);
  let desc = 0, aviso = '';
  if (c && c.minimo && sub < c.minimo) aviso = `El cupón ${c.codigo} requiere una compra mínima de ${money(c.minimo)}.`;
  else if (c) desc = c.tipo === 'porcentaje' ? Math.round(sub * c.valor / 100) : Math.min(c.valor, sub);
  return { lineas, sub, desc, aviso, total: sub - desc, cupon: c };
}

function agregar(t, id, color = '', cap = '') {
  const key = [t, id, color, cap].join('|'), i = items.find(x => x.key === key);
  i ? i.qty = Math.min(i.qty + 1, 10) : items.push({ key, t, id, color, cap, qty: 1 });
  guardar(); pintar();
}
const vaciar = () => { items = []; cupon = null; guardar(); pintar(); };

function pintar() {
  const t = totales(), n = t.lineas.reduce((s, l) => s + l.qty, 0);
  $('#cartCount').textContent = n; $('#cartCount').hidden = !n;
  $('#cartLines').innerHTML = n ? `<ul class="cl-list">${t.lineas.map(l => `<li class="cl">
      ${l.img ? `<img src="${l.img}" alt="">` : `<span class="ico">${l.ico}</span>`}
      <div><b>${esc(l.nombre)}</b><br><small class="muted">${esc(l.det)}</small><br>${money(l.precio)}</div>
      <div class="qty"><button data-c="menos" data-k="${esc(l.key)}" aria-label="Quitar una unidad">−</button><output>${l.qty}</output>
      <button data-c="mas" data-k="${esc(l.key)}" aria-label="Añadir una unidad">+</button>
      <button data-c="del" data-k="${esc(l.key)}" aria-label="Eliminar ${esc(l.nombre)}">✕</button></div></li>`).join('')}</ul>`
    : '<p class="muted">Tu carrito está vacío. Elige un luchador y añádelo a tu equipo.</p>';
  $('#cartTotals').innerHTML = `<div><dt>Subtotal</dt><dd>${money(t.sub)}</dd></div>
    ${t.desc ? `<div><dt>Cupón ${t.cupon.codigo} <button class="link" data-c="quitar-cupon">Quitar</button></dt><dd>−${money(t.desc)}</dd></div>` : ''}
    <div><dt>Envío</dt><dd>Gratis</dd></div><div class="t"><dt>Total</dt><dd>${money(t.total)}</dd></div>`;
  const m = $('#couponMsg'); m.textContent = t.aviso; m.className = t.aviso ? 'bad' : '';
  $('#checkout').disabled = !n;
}

function initCart(alPagar) {
  $('#cartDrawer').addEventListener('click', e => {           // + / − / eliminar / quitar cupón
    const b = e.target.closest('[data-c]'); if (!b) return;
    const it = items.find(x => x.key === b.dataset.k), a = b.dataset.c;
    if (it && a === 'mas') it.qty = Math.min(it.qty + 1, 10);
    if (it && a === 'menos') it.qty--;
    if (it && a === 'del') it.qty = 0;
    if (a === 'quitar-cupon') cupon = null;
    items = items.filter(x => x.qty > 0); guardar(); pintar();
  });
  $('#couponForm').addEventListener('submit', e => {          // validación de cupones
    e.preventDefault();
    const code = $('#couponInput').value.trim().toUpperCase(), c = DATA.cupones.find(x => x.codigo === code), m = $('#couponMsg');
    const avisar = (txt, mal) => { m.textContent = txt; m.className = mal ? 'bad' : ''; };
    if (!code) return avisar('Escribe un código para aplicarlo.', 1);
    if (!c) return avisar('Ese cupón no existe. Revisa que esté bien escrito.', 1);
    if (c.minimo && totales().sub < c.minimo) return avisar(`Este cupón requiere una compra mínima de ${money(c.minimo)}.`, 1);
    cupon = c.codigo; guardar(); pintar(); avisar(`Listo: ${c.descripcion}.`); $('#couponInput').value = '';
  });
  $('#checkout').addEventListener('click', () => alPagar(totales()));
  pintar();
}
