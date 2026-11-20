/* core.js (script clásico: sin import/export, se carga primero): utilidades, almacenamiento seguro, carga del catálogo y generador de imágenes */
const $ = (s, c = document) => c.querySelector(s);
const $$ = (s, c = document) => [...c.querySelectorAll(s)];
const esc = s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`); // evita inyección de HTML
const norm = s => String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
const API_BASE = ''; // vacío = mismo servidor (python server/servidor.py). Si el API vive en otro dominio, pon aquí su URL.
const fmt = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
const money = n => fmt.format(n); // cambia moneda y localidad aquí

/* LocalStorage (persistente) y SessionStorage (solo la pestaña), con prefijo y a prueba de errores */
const K = 'energysmash:';
const almacen = area => ({
  get: (k, d = null) => { try { const v = area().getItem(K + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set: (k, v) => { try { area().setItem(K + k, JSON.stringify(v)); } catch {} },
  del: k => { try { area().removeItem(K + k); } catch {} },
});
const local = almacen(() => localStorage);
const temp = almacen(() => sessionStorage);

/* Catálogo: se llena al leer productos.json */
let DATA = { marcas: [], perfiles: [], productos: [], accesorios: [], guias: [], cupones: [] };
async function loadCatalog() {
  try {
    const r = await fetch('productos.json');
    if (!r.ok) throw new Error(`productos.json respondió ${r.status}`);
    DATA = await r.json();
  } catch (err) {
    // Abierto con doble clic (file://) el navegador bloquea fetch: se usa la copia de js/productos-respaldo.js
    if (!window.PRODUCTOS_RESPALDO) throw err;
    DATA = window.PRODUCTOS_RESPALDO;
    console.info('Catálogo cargado desde js/productos-respaldo.js (sin servidor). Con servidor se lee productos.json.');
  }
  soloFotosReales(); // regla de la tienda: un celular sin fotos reales no se muestra
}
const soloFotosReales = () => { DATA.productos = DATA.productos.filter(p => p.colores?.length && p.colores.every(c => c.imagenes?.length)); };
const prod = id => DATA.productos.find(p => p.id === id);
const acc = id => DATA.accesorios.find(a => a.id === id);
const marca = id => DATA.marcas.find(m => m.id === id)?.nombre ?? id;
const precio = (p, cap) =>
  Math.round(p.precioBase * (1 - (p.oferta?.descuento || 0) / 100)) + (p.capacidades.find(c => c.id === cap)?.extra || 0);

/* Galería por color: solo fotos reales ("imagenes": ["assets/img/reales/x.jpg", ...]). No se dibuja nada de relleno. */
const imagenes = (p, colorId) => (p.colores.find(x => x.id === colorId) || p.colores[0]).imagenes;
