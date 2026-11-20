/* auth.js: inicio de sesión simulado (modal) + mensaje de bienvenida del bot.
   Solo se guardan correo y nombre; la contraseña se valida y se descarta. */

let user = temp.get('usuario') ?? local.get('usuario');
const usuario = () => user;

function cabecera() {
  $('#userLabel').textContent = user ? user.nombre : 'Ingresar';
  $('#userAvatar').textContent = user ? user.nombre[0].toUpperCase() : '?';
}

function abrirAuth() {
  $('#authOut').hidden = !!user; $('#authIn').hidden = !user;
  if (user) { $('#authName').textContent = user.nombre; $('#authMail').textContent = user.email; }
  $('#authDialog').showModal();
}

function initAuth() {
  cabecera();
  const f = $('#authForm');
  f.addEventListener('submit', e => {
    e.preventDefault();
    const d = new FormData(f), email = d.get('email').trim().toLowerCase(), pass = d.get('password');
    const eE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) ? '' : 'Escribe un correo válido, por ejemplo tu@correo.com.';
    const eP = pass.length >= 6 ? '' : 'La contraseña necesita al menos 6 caracteres.';
    $('#errEmail').textContent = eE; $('#errPass').textContent = eP;
    if (eE || eP) return;
    const nombre = email.split('@')[0].split(/[._\-+\d]+/)[0] || 'Luchador';
    user = { email, nombre: nombre[0].toUpperCase() + nombre.slice(1) };
    local.del('usuario'); temp.del('usuario');
    (d.get('remember') ? local : temp).set('usuario', user);   // "Mantener sesión" decide dónde se guarda
    f.reset(); $('#authDialog').close(); cabecera(); bienvenida(user.nombre);
  });
  $('#logout').addEventListener('click', () => { user = null; local.del('usuario'); temp.del('usuario'); cabecera(); $('#authDialog').close(); });
  $('#botClose').addEventListener('click', () => { $('#bot').hidden = true; });
}

function bienvenida(nombre) {
  const log = $('#botLog'); log.replaceChildren(); $('#bot').hidden = false;
  [`¡Hola, ${nombre}! Soy SmashBot y te doy la bienvenida a la arena.`,
   'Tu primer combo: usa el cupón SMASH10 en el carrito y llévate 10% de descuento.',
   'Empieza por las ofertas flash: se acaban cuando el reloj llega a cero.']
    .forEach((m, i) => setTimeout(() => { const p = document.createElement('p'); p.textContent = m; log.append(p); log.scrollTop = log.scrollHeight; }, 700 * (i + 1)));
}
