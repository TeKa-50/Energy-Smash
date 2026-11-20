/* devoluciones.js: solicitud de devolución funcional. Usa los pedidos que guarda la tienda al finalizar
   una compra (LocalStorage) y registra cada solicitud con un folio DV-XXXXXX. */
const VENTANA_DIAS = 30;
const pedidos = () => local.get('pedidos', []);
const solicitudes = () => local.get('devoluciones', []);
const fechaCorta = iso => new Date(iso).toLocaleDateString('es-MX', { day: 'numeric', month: 'long', year: 'numeric' });
const diasDesde = iso => Math.floor((Date.now() - new Date(iso)) / 864e5);
const yaSolicitados = folio => solicitudes().filter(s => s.folio === folio).flatMap(s => s.indices);

function pintarPedidos() {
  const ps = pedidos();
  $('#rmaForm').hidden = !ps.length; $('#rmaVacio').hidden = !!ps.length;
  $('#rmaFolio').innerHTML = ps.map(p => `<option value="${esc(p.folio)}">${esc(p.folio)}, ${fechaCorta(p.fecha)}, ${money(p.total)}</option>`).join('');
  $('#pedidosList').innerHTML = ps.length ? ps.map(p => `<article class="panel"><b>${esc(p.folio)}</b> <span class="muted">${fechaCorta(p.fecha)}</span>
    <ul>${p.lineas.map(l => `<li>${esc(l.nombre)} (${esc(l.det)}) × ${l.qty}</li>`).join('')}</ul><b>Total: ${money(p.total)}</b></article>`).join('')
    : '<p class="muted">Aún no tienes pedidos en este navegador.</p>';
  pintarLineas();
}
function pintarLineas() {
  const p = pedidos().find(x => x.folio === $('#rmaFolio').value); if (!p) return;
  const hechas = yaSolicitados(p.folio);
  $('#rmaLineas').innerHTML = '<legend>Artículos a devolver</legend>' + p.lineas.map((l, i) =>
    `<label class="chk"><input type="checkbox" name="linea" value="${i}"${hechas.includes(i) ? ' disabled' : ''}> ${esc(l.nombre)} (${esc(l.det)}) × ${l.qty}${hechas.includes(i) ? ' <small class="muted">ya solicitado</small>' : ''}</label>`).join('');
}
function pintarSolicitudes() {
  const ss = solicitudes();
  $('#rmaList').innerHTML = ss.length ? ss.map(s => `<article class="panel"><b>${esc(s.rma)}</b> <span class="muted">${fechaCorta(s.fecha)}</span> <span class="tag">${esc(s.estado)}</span>
    <p>Pedido ${esc(s.folio)}: ${s.articulos.map(esc).join(', ')}</p><p class="muted">Motivo: ${esc(s.motivo)}</p></article>`).join('')
    : '<p class="muted">Aún no has enviado solicitudes.</p>';
}

$('#rmaFolio').addEventListener('change', pintarLineas);
$('#rmaForm').addEventListener('submit', e => {
  e.preventDefault();
  const f = e.target, err = $('#rmaErr'), p = pedidos().find(x => x.folio === f.folio.value);
  const idx = [...f.querySelectorAll('[name=linea]:checked')].map(c => +c.value);
  err.textContent = '';
  if (!p) return void (err.textContent = 'Elige un pedido.');
  if (!idx.length) return void (err.textContent = 'Marca al menos un artículo para devolver.');
  if (diasDesde(p.fecha) > VENTANA_DIAS) return void (err.textContent = `Este pedido tiene ${diasDesde(p.fecha)} días y la ventana de devolución es de ${VENTANA_DIAS}. Escríbenos para revisar tu caso.`);
  if (!f.estado.checked) return void (err.textContent = 'Confirma que el producto está en buen estado y con sus accesorios.');
  const rma = 'DV-' + Math.random().toString(36).slice(2, 8).toUpperCase();
  local.set('devoluciones', [{ rma, folio: p.folio, indices: idx, articulos: idx.map(i => p.lineas[i].nombre), motivo: f.motivo.value,
    coment: f.coment.value.trim().slice(0, 500), fecha: new Date().toISOString(), estado: 'En revisión' }, ...solicitudes()]);
  f.reset(); pintarLineas(); pintarSolicitudes();
  const ok = $('#rmaOk'); ok.hidden = false; ok.textContent = `Solicitud ${rma} registrada. Revisaremos tu caso en 2 días hábiles y te escribiremos con los siguientes pasos.`;
});
pintarPedidos(); pintarSolicitudes();
