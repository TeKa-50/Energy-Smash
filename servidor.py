import json, os, re, secrets, smtplib, ssl, sys, threading, time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
DATOS = AQUI / 'datos'
BLOQUEO = threading.Lock()
EMAIL_RE = re.compile(r'^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]{2,}$')

def cargar_env():
    f = AQUI / '.env'
    if f.exists():
        for linea in f.read_text(encoding='utf-8').splitlines():
            linea = linea.strip()
            if linea and not linea.startswith('#') and '=' in linea:
                k, v = linea.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))
cargar_env()
cfg = lambda k, d='': os.environ.get(k, d)
sitio = lambda: cfg('SITIO_URL', 'http://localhost:8000').rstrip('/')

# ---------- suscriptores (archivo JSON) ----------
def leer():
    f = DATOS / 'suscriptores.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
def guardar(d):
    DATOS.mkdir(exist_ok=True)
    tmp = DATOS / 'suscriptores.json.tmp'
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(DATOS / 'suscriptores.json')
ahora = lambda: datetime.now(timezone.utc).isoformat(timespec='seconds')

# ---------- envío de correo ----------
def enviar(destino, asunto, texto, html, baja_url=None):
    msg = EmailMessage()
    msg['Subject'], msg['To'] = asunto, destino
    msg['From'] = cfg('MAIL_FROM') or f"Energy Smash <{cfg('SMTP_USUARIO') or 'ofertas@localhost'}>"
    msg['Date'], msg['Message-ID'] = formatdate(localtime=True), make_msgid()
    if baja_url: msg['List-Unsubscribe'] = f'<{baja_url}>'
    msg.set_content(texto); msg.add_alternative(html, subtype='html')
    host = cfg('SMTP_HOST')
    if not host:   # modo simulación: se guarda el correo en lugar de enviarlo
        bandeja = DATOS / 'bandeja'; bandeja.mkdir(parents=True, exist_ok=True)
        (bandeja / f"{int(time.time() * 1000)}-{re.sub(r'[^a-z0-9]+', '_', destino.lower())}.eml").write_bytes(bytes(msg))
        return 'simulado'
    puerto = int(cfg('SMTP_PUERTO', '587'))
    seg = cfg('SMTP_SEGURIDAD', 'ssl' if puerto == 465 else 'starttls').lower()   # ssl | starttls | ninguna
    ctx = ssl.create_default_context()
    s = smtplib.SMTP_SSL(host, puerto, timeout=20, context=ctx) if seg == 'ssl' else smtplib.SMTP(host, puerto, timeout=20)
    with s:
        s.ehlo()
        if seg == 'starttls': s.starttls(context=ctx); s.ehlo()
        if cfg('SMTP_USUARIO'): s.login(cfg('SMTP_USUARIO'), cfg('SMTP_CLAVE'))
        s.send_message(msg)
    return 'enviado'

# ---------- plantillas de correo ----------
def plantilla(titulo, cuerpo_html, pie):
    return f'''<!DOCTYPE html><html lang="es"><body style="margin:0;background:#f2f2f5;font-family:Arial,Helvetica,sans-serif;color:#17171c">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff">
<tr><td style="background:#111115;padding:20px 24px;border-bottom:4px solid #E60012"><span style="color:#fff;font-size:24px;font-weight:bold;font-style:italic">ENERGY <span style="color:#E60012">SMASH</span></span></td></tr>
<tr><td style="padding:28px 24px"><h1 style="margin:0 0 14px;font-size:24px">{titulo}</h1>{cuerpo_html}</td></tr>
<tr><td style="padding:16px 24px;background:#f7f7fa;color:#6a6a78;font-size:12px;line-height:1.5">{pie}</td></tr>
</table></td></tr></table></body></html>'''
boton = lambda url, txt: f'<p style="margin:22px 0"><a href="{escape(url)}" style="background:#E60012;color:#fff;text-decoration:none;font-weight:bold;padding:12px 24px;display:inline-block">{escape(txt)}</a></p>'
dinero = lambda n: f'${n:,.0f}'

def correo_confirmacion(sub):
    url = f"{sitio()}/api/confirmar?t={sub['token_confirmar']}"
    texto = f'Confirma tu suscripción a las ofertas de Energy Smash abriendo este enlace:\n{url}\n\nSi no fuiste tú, ignora este mensaje y no recibirás nada.'
    html = plantilla('Confirma tu suscripción', '<p style="font-size:15px;line-height:1.5">Solo falta un paso para recibir nuestras ofertas flash y lanzamientos.</p>' + boton(url, 'Confirmar mi suscripción')
                     + '<p style="font-size:13px;color:#6a6a78">Si no fuiste tú, ignora este mensaje y no recibirás nada.</p>', 'Recibes este correo porque alguien pidió suscribir esta dirección en Energy Smash.')
    return 'Confirma tu suscripción a Energy Smash', texto, html

def ofertas_actuales():
    productos = json.loads((RAIZ / 'productos.json').read_text(encoding='utf-8'))['productos']
    lista = []
    for p in productos:
        if p.get('oferta'):
            d = p['oferta']['descuento']
            lista.append((p['nombre'], p['marca'], p['precioBase'], round(p['precioBase'] * (1 - d / 100)), d))
    return sorted(lista, key=lambda x: -x[4])[:8]

def correo_ofertas(ofertas, baja_url):
    marcas = {m['id']: m['nombre'] for m in json.loads((RAIZ / 'productos.json').read_text(encoding='utf-8'))['marcas']}
    filas = ''.join(f'<tr><td style="padding:10px 0;border-bottom:1px solid #e6e6ec"><b>{escape(n)}</b><br><span style="color:#6a6a78;font-size:13px">{escape(marcas.get(m, m))}</span></td>'
                    f'<td align="right" style="padding:10px 0;border-bottom:1px solid #e6e6ec"><s style="color:#8a8a96;font-size:13px">{dinero(a)}</s><br><b style="font-size:17px">{dinero(b)}</b> '
                    f'<span style="background:#E60012;color:#fff;font-size:12px;padding:1px 6px">-{d}%</span></td></tr>' for n, m, a, b, d in ofertas)
    cuerpo = ('<p style="font-size:15px;line-height:1.5">Estas son las ofertas flash de hoy. Duran hasta agotar existencias.</p>'
              f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas}</table>' + boton(f'{sitio()}/#ofertas', 'Ver las ofertas'))
    pie = (f'Recibes este correo porque confirmaste tu suscripción en Energy Smash. <a href="{escape(baja_url)}" style="color:#6a6a78">Cancelar suscripción</a>.'
           + (f"<br>{escape(cfg('EMPRESA_DIRECCION'))}" if cfg('EMPRESA_DIRECCION') else ''))
    texto = 'Ofertas flash de Energy Smash\n\n' + '\n'.join(f'- {n}: {dinero(b)} (antes {dinero(a)}, -{d}%)' for n, _, a, b, d in ofertas) \
            + f'\n\nVer ofertas: {sitio()}/#ofertas\n\nPara cancelar tu suscripción: {baja_url}'
    return cfg('ASUNTO_OFERTAS', 'Ofertas flash de Energy Smash'), texto, plantilla('Ofertas flash de hoy', cuerpo, pie)

def enviar_ofertas():
    ofertas = ofertas_actuales()
    if not ofertas: return {'ok': False, 'mensaje': 'No hay productos con "oferta" en productos.json.'}
    with BLOQUEO: confirmados = [s for s in leer().values() if s['estado'] == 'confirmado']
    r = {'ok': True, 'destinatarios': len(confirmados), 'enviados': 0, 'simulados': 0, 'fallidos': []}
    for s in confirmados:
        try:
            asunto, texto, html = correo_ofertas(ofertas, f"{sitio()}/api/baja?t={s['token_baja']}")
            res = enviar(s['email'], asunto, texto, html, f"{sitio()}/api/baja?t={s['token_baja']}")
            r['simulados' if res == 'simulado' else 'enviados'] += 1
        except Exception as e:
            r['fallidos'].append({'email': s['email'], 'error': str(e)[:120]})
    return r

# ---------- servidor HTTP ----------
INTENTOS = {}   # límite sencillo por IP para que nadie use el formulario para saturar buzones
def permitido(ip, maximo=5, ventana=600):
    t = time.time(); lista = [x for x in INTENTOS.get(ip, []) if t - x < ventana]
    INTENTOS[ip] = lista + [t]
    return len(lista) < maximo

class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(RAIZ), **k)
    def log_request(self, code='-', size='-'): print(f"{self.command} {self.path.split('?')[0]} {code}")
    def responder(self, codigo, obj):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(codigo); self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(cuerpo))); self.end_headers(); self.wfile.write(cuerpo)
    def redirigir(self, destino):
        self.send_response(302); self.send_header('Location', destino); self.end_headers()

    def do_GET(self):
        u = urlparse(self.path); partes = [p for p in unquote(u.path).split('/') if p]
        if u.path.startswith('/api/'):
            t = parse_qs(u.query).get('t', [''])[0]
            if u.path == '/api/confirmar': return self.redirigir('/boletin.html?estado=' + self.cambiar_estado(t, 'token_confirmar', 'confirmado'))
            if u.path == '/api/baja': return self.redirigir('/boletin.html?estado=' + self.cambiar_estado(t, 'token_baja', 'baja'))
            return self.responder(404, {'mensaje': 'No encontrado.'})
        if any(p.startswith('.') or p in ('server', 'tools') for p in partes[:1]) or any(p.startswith('.') for p in partes):
            return self.send_error(404)   # no exponer .env, datos de suscriptores ni scripts
        super().do_GET()
    do_HEAD = do_GET

    def cambiar_estado(self, token, campo, estado):
        if not token: return 'invalido'
        with BLOQUEO:
            d = leer(); sub = next((s for s in d.values() if s.get(campo) == token), None)
            if not sub or (campo == 'token_confirmar' and sub['estado'] == 'baja'): return 'invalido'   # un enlace viejo no reactiva una baja
            sub['estado'] = estado; sub[estado + '_fecha'] = ahora(); guardar(d)
        return estado

    def do_POST(self):
        ruta = urlparse(self.path).path
        try: datos = json.loads(self.rfile.read(min(int(self.headers.get('Content-Length', 0)), 4000)) or b'{}')
        except Exception: return self.responder(400, {'mensaje': 'Solicitud no válida.'})
        if ruta == '/api/suscribir': return self.suscribir(datos)
        if ruta == '/api/admin/enviar-ofertas':
            token = cfg('ADMIN_TOKEN')
            if not token: return self.responder(403, {'mensaje': 'Define ADMIN_TOKEN en server/.env para usar este endpoint.'})
            if not secrets.compare_digest(self.headers.get('Authorization', ''), f'Bearer {token}'): return self.responder(401, {'mensaje': 'No autorizado.'})
            return self.responder(200, enviar_ofertas())
        self.responder(404, {'mensaje': 'No encontrado.'})

    def suscribir(self, datos):
        email = str(datos.get('email', '')).strip().lower()
        if not datos.get('consentimiento'): return self.responder(400, {'mensaje': 'Marca la casilla para aceptar el aviso de privacidad.'})
        if len(email) > 254 or not EMAIL_RE.match(email): return self.responder(400, {'mensaje': 'Escribe un correo válido, por ejemplo tu@correo.com.'})
        if not permitido(self.client_address[0]): return self.responder(429, {'mensaje': 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.'})
        with BLOQUEO:
            d = leer(); sub = d.get(email)
            if sub and sub['estado'] == 'confirmado': return self.responder(200, {'ok': True, 'mensaje': 'Este correo ya está suscrito. ¡Gracias!'})
            d[email] = sub = {'email': email, 'estado': 'pendiente', 'token_confirmar': secrets.token_urlsafe(24), 'token_baja': (sub or {}).get('token_baja') or secrets.token_urlsafe(24),
                              'consentimiento_fecha': ahora(), 'creado': (sub or {}).get('creado', ahora())}
            guardar(d)
        try:
            res = enviar(email, *correo_confirmacion(sub))
        except Exception as e:
            print('Error al enviar correo de confirmación:', e)
            return self.responder(502, {'mensaje': 'No pudimos enviar el correo de confirmación. Inténtalo más tarde.'})
        extra = ' (modo simulación: el correo quedó en server/datos/bandeja)' if res == 'simulado' else ''
        self.responder(200, {'ok': True, 'mensaje': 'Te enviamos un correo para confirmar tu suscripción. Revisa también tu carpeta de spam.' + extra})

def main():
    orden = sys.argv[1] if len(sys.argv) > 1 else 'servir'
    if orden == 'ofertas': print(json.dumps(enviar_ofertas(), ensure_ascii=False, indent=1))
    elif orden == 'suscriptores':
        for s in leer().values(): print(f"{s['estado']:<10} {s['email']}")
    else:
        puerto = int(cfg('PUERTO', '8000'))
        print(f"Energy Smash en {sitio()}  (puerto {puerto})\nCorreo: {'SMTP ' + cfg('SMTP_HOST') if cfg('SMTP_HOST') else 'SIMULACIÓN (se guarda en server/datos/bandeja)'}\n"
              f"Envío de ofertas por API: {'activado' if cfg('ADMIN_TOKEN') else 'desactivado (define ADMIN_TOKEN)'}\nCtrl+C para detener.")
        ThreadingHTTPServer(('', puerto), Manejador).serve_forever()

if __name__ == '__main__':
    main()
