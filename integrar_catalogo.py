
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI))

JSON_TIENDA = RAIZ / "productos.json"
JS_RESPALDO = RAIZ / "js" / "productos-respaldo.js"
CARPETA_IMG = RAIZ / "assets" / "img" / "reales"
CARPETA_RESPALDO = RAIZ / "respaldo"
CRUDO = AQUI / "salida" / "gsmarena_crudo.json"

EXTRA_POR_ESCALON = 0.10   # GSMArena da un solo precio: cada capacidad mayor suma este % (editable con --extra)
MAX_COLORES = 3
MAX_FOTOS = 3

# palabra del color (inglés) -> hex. Se prueba en este orden; si nada coincide se usa gris.
HEX_COLORES = [
    ("black", "#26262b"), ("midnight", "#26262b"), ("white", "#e9edf2"), ("starlight", "#e9e4d8"),
    ("silver", "#c9ccd1"), ("blue", "#4f7fb5"), ("green", "#6f8f72"), ("red", "#e0302a"),
    ("pink", "#d98fa6"), ("purple", "#8a73c4"), ("violet", "#8a73c4"), ("lavender", "#8a73c4"), ("lilac", "#8a73c4"),
    ("gold", "#c9a24b"), ("yellow", "#d8b84a"), ("orange", "#e8803a"), ("coral", "#e8803a"),
    ("mint", "#7fc4a8"), ("teal", "#2aa6a6"), ("cyan", "#2aa6a6"), ("turquoise", "#2aa6a6"),
    ("bronze", "#8a6a4a"), ("brown", "#8a6a4a"), ("cream", "#d8cfc0"), ("natural", "#b9b2a6"), ("beige", "#d8cfc0"),
    ("gray", "#4a5058"), ("grey", "#4a5058"), ("graphite", "#4a5058"), ("titanium", "#8d8f94"),
]
GRIS = "#6b7280"
GAMER_CHIP = re.compile(r"Snapdragon 8|Dimensity [89]|Tensor|Apple A1[5-9]|Apple A[2-9]\d|Exynos 2[2-9]", re.I)


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def hex_de(nombre: str) -> str:
    n = nombre.lower()
    return next((h for palabra, h in HEX_COLORES if palabra in n), GRIS)


def numero(patron: str, texto: str) -> float | None:
    m = re.search(patron, texto or "", re.I)
    return float(m.group(1)) if m else None


# ---------- conversión de un celular crudo -> formato de la tienda ----------
def parsear_memoria(texto: str) -> tuple[list[int], int]:
    """'256GB 12GB RAM, 1TB 12GB RAM' -> ([256, 1024], 12). Devuelve almacenamientos en GB y la RAM máxima."""
    gb, ram = [], 0
    for alm, unidad, r in re.findall(r"(\d+)\s*(GB|TB)\s+(\d+)\s*GB\s*RAM", texto or "", re.I):
        cap = int(alm) * (1024 if unidad.upper() == "TB" else 1)
        if cap not in gb:
            gb.append(cap)
        ram = max(ram, int(r))
    if not gb:  # formato sin RAM, p. ej. "128GB, 256GB"
        for alm, unidad in re.findall(r"(\d+)\s*(GB|TB)", texto or "", re.I):
            cap = int(alm) * (1024 if unidad.upper() == "TB" else 1)
            if cap not in gb and cap >= 16:
                gb.append(cap)
    return sorted(gb)[:4], ram


def etiqueta_cap(gb: int) -> str:
    return f"{gb // 1024} TB" if gb >= 1024 and gb % 1024 == 0 else f"{gb} GB"


def precio_tienda(mxn: float) -> int:
    """Redondea al estilo de la tienda (…99): 16,284 -> 16,299."""
    return max(99, int(round(mxn / 100.0)) * 100 - 1)


def construir_colores(c: dict, rutas: dict[str, str]) -> list[dict]:
    """Un color por nombre oficial (máx. 3). Cada color arranca su galería en una foto distinta."""
    nombres = [x.strip() for x in c["crudo"].get("colores", "").split(",") if x.strip()][:MAX_COLORES] or ["Estándar"]
    fotos = [rutas[u] for u in dict.fromkeys(c.get("imagenes") or []) if u in rutas]  # solo fotos ya descargadas
    colores, usados = [], set()
    for k, nombre in enumerate(nombres):
        cid = slug(nombre) or f"color-{k + 1}"
        if cid in usados:
            cid = f"{cid}-{k + 1}"
        usados.add(cid)
        col = {"id": cid, "nombre": nombre, "hex": hex_de(nombre)}
        rot = fotos[k % len(fotos):] + fotos[:k % len(fotos)]
        col["imagenes"] = rot[:MAX_FOTOS]
        colores.append(col)
    return colores


def perfiles_de(nombre: str, marca: str, mxn: float, bateria: float | None, mp: float | None, ram: int, chip: str) -> list[str]:
    """Heurística sencilla (editable): GSMArena no trae 'perfiles', así que se deducen de las specs."""
    p = []
    if GAMER_CHIP.search(chip or "") or ram >= 12:
        p.append("gamer")
    if (mp or 0) >= 100 or marca in ("Apple", "Google") or re.search(r"\b(Ultra|Pro)\b", nombre):
        p.append("fotografia")
    if (bateria or 0) >= 5000:
        p.append("bateria")
    if mxn >= 9000:
        p.append("trabajo")
    if mxn < 8000:
        p.append("economico")
    return p or ["trabajo"]


def convertir(c: dict, rutas: dict[str, str], extra: float) -> dict:
    raw, marca = c["crudo"], c["marca"]
    nombre = c["nombre"][len(marca):].strip() if c["nombre"].lower().startswith(marca.lower()) else c["nombre"]
    mxn = float(c["precio"])
    gbs, ram = parsear_memoria(raw.get("memoria", ""))
    base = precio_tienda(mxn)
    capacidades = [{"id": etiqueta_cap(g), "extra": round(base * extra * i / 100.0) * 100} for i, g in enumerate(gbs)] \
        or [{"id": "Único", "extra": 0}]
    pulgadas, mp, mah = numero(r"([\d.]+)\s*inches", raw.get("pantalla", "")), numero(r"([\d.]+)\s*MP", raw.get("camara", "")), \
        numero(r"(\d{4,5})\s*mAh", raw.get("bateria", ""))
    specs = [s for s in (
        f'{pulgadas:g}" pantalla' if pulgadas else "", f"{ram} GB RAM" if ram else "",
        f"{mp:g} MP" if mp else "", f"{mah:.0f} mAh" if mah else "", "5G" if "5G" in raw.get("red", "") else "") if s]
    return {
        "id": slug(f"{marca} {nombre}"), "marca": slug(marca), "nombre": nombre,
        "descripcion": c["descripcion"], "precioBase": base,
        "perfiles": perfiles_de(nombre, marca, mxn, mah, mp, ram, raw.get("procesador", "")),
        "specs": specs or ["Smartphone"], "capacidades": capacidades,
        "colores": construir_colores(c, rutas), "fuente": c.get("url", ""),
    }


# ---------- imágenes ----------
MIN_BYTES = 3000  # menos que esto es un icono o un marcador, no una foto
MAGIA = (b"\xff\xd8\xff", b"\x89PNG", b"RIFF", b"GIF8")  # JPG, PNG, WEBP, GIF


def es_foto(datos: bytes) -> bool:
    return len(datos) >= MIN_BYTES and datos.startswith(MAGIA)


def descargar_imagenes(crudos: list[dict]) -> dict[str, str]:
    """Baja cada URL de foto a assets/img/reales/ (3 intentos) y devuelve {url: ruta_relativa} solo de las que sí son fotos válidas."""
    import requests
    import web  # headers y User-Agent del scraper

    CARPETA_IMG.mkdir(parents=True, exist_ok=True)
    rutas, fallidas = {}, 0
    with requests.Session() as s:
        for c in crudos:
            base = slug(c["nombre"])
            for n, url in enumerate(dict.fromkeys(c.get("imagenes") or []), start=1):
                if url in rutas:
                    continue
                ext = Path(urlparse(url).path).suffix.lower() or ".jpg"
                destino = CARPETA_IMG / f"{base}-{n}{ext}"
                if destino.exists() and es_foto(destino.read_bytes()):
                    rutas[url] = destino.relative_to(RAIZ).as_posix()
                    continue
                for intento in range(3):
                    try:
                        time.sleep(0.25 + intento)
                        r = s.get(url, headers={**web.HEADERS, "Referer": web.BASE_URL}, timeout=20)
                        r.raise_for_status()
                        if not es_foto(r.content):
                            raise ValueError("el archivo no es una foto válida")
                        destino.write_bytes(r.content)
                        rutas[url] = destino.relative_to(RAIZ).as_posix()
                        break
                    except Exception as exc:  # noqa: BLE001
                        if intento == 2:
                            fallidas += 1
                            print(f"  [!] No se pudo bajar {url}: {exc}")
    print(f"Fotos descargadas: {len(rutas)} (fallidas: {fallidas}) -> {CARPETA_IMG.relative_to(RAIZ)}/")
    return rutas


# ---------- escritura ----------
def serializar(d: dict) -> str:
    """JSON compacto, un elemento de lista por línea (mismo estilo que el original)."""
    bloques = []
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            cuerpo = "[\n" + ",\n".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in v) + "\n]"
        else:
            cuerpo = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        bloques.append(f'"{k}":{cuerpo}')
    return "{\n" + ",\n".join(bloques) + "\n}"


def respaldar() -> None:
    CARPETA_RESPALDO.mkdir(exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    for f in (JSON_TIENDA, JS_RESPALDO):
        if f.exists():
            shutil.copy2(f, CARPETA_RESPALDO / f"{f.stem}-{sello}{f.suffix}")
    print(f"Respaldo previo guardado en {CARPETA_RESPALDO.relative_to(RAIZ)}/ ({sello})")


def auditar(productos: list[dict]) -> list[str]:
    """Todo color de todo celular debe tener fotos reales que existan en disco."""
    errores = []
    for p in productos:
        for c in p["colores"]:
            fotos = c.get("imagenes") or []
            if not fotos:
                errores.append(f"{p['id']}: el color {c['nombre']} no tiene fotos")
            errores += [f"{p['id']}: falta {r}" for r in fotos if not (RAIZ / r).is_file()]
    return errores


def main() -> None:
    ap = argparse.ArgumentParser(description="Integra celulares reales de GSMArena al catálogo de Energy Smash")
    ap.add_argument("-t", "--total", type=int, default=50, help="celulares a extraer (por defecto 50)")
    ap.add_argument("--desde", type=Path, help="JSON crudo de un scrapeo anterior (omite el scrapeo)")
    ap.add_argument("--ofertas", type=int, default=6, help="cuántos productos entran a ofertas flash (por defecto 6)")
    ap.add_argument("--extra", type=float, default=EXTRA_POR_ESCALON, help="recargo por cada capacidad mayor (0.10 = 10%%)")
    a = ap.parse_args()

    if a.desde:
        crudos = json.loads(a.desde.read_text(encoding="utf-8"))
    else:
        import web
        crudos = web.scrapear(a.total)
        CRUDO.parent.mkdir(parents=True, exist_ok=True)
        CRUDO.write_text(json.dumps(crudos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Datos crudos guardados en {CRUDO.relative_to(RAIZ)}")
    if not crudos:
        sys.exit("No se obtuvo ningún celular; no se modificó nada.")

    rutas = descargar_imagenes(crudos)
    con_fotos = [c for c in crudos if any(u in rutas for u in (c.get("imagenes") or []))]
    for c in crudos:
        if c not in con_fotos:
            print(f"  [!] Descartado (sin fotos reales): {c['nombre']}")
    crudos = con_fotos
    if not crudos:
        sys.exit("Ningún celular quedó con fotos reales; no se modificó nada.")
    productos = [convertir(c, rutas, a.extra) for c in crudos]

    ids = set()
    for p in productos:  # ids únicos
        base, n = p["id"], 2
        while p["id"] in ids:
            p["id"], n = f"{base}-{n}", n + 1
        ids.add(p["id"])

    rnd = random.Random(2026)  # promociones: decisión de la tienda, no dato del scraper
    for p in rnd.sample(productos, min(a.ofertas, len(productos))):
        p["oferta"] = {"descuento": rnd.choice([10, 15, 20, 25]), "vendido": rnd.randint(40, 90)}
    productos[0]["nuevo"] = True

    previo = json.loads(JSON_TIENDA.read_text(encoding="utf-8")) if JSON_TIENDA.exists() else {}
    marcas, vistas = [], set()
    for c in crudos:
        if slug(c["marca"]) not in vistas:
            vistas.add(slug(c["marca"]))
            marcas.append({"id": slug(c["marca"]), "nombre": c["marca"]})
    catalogo = {"marcas": marcas, "perfiles": previo.get("perfiles", []), "productos": productos,
                "accesorios": previo.get("accesorios", []), "guias": previo.get("guias", []), "cupones": previo.get("cupones", [])}

    errores = auditar(productos)
    if errores:
        sys.exit("Auditoría fallida, no se modificó el catálogo:\n  " + "\n  ".join(errores))

    respaldar()
    texto = serializar(catalogo)
    JSON_TIENDA.write_text(texto + "\n", encoding="utf-8")
    JS_RESPALDO.write_text("/* Copia de productos.json para abrir la tienda sin servidor. Se regenera con scripts/integrar_catalogo.py. */\n"
                           f"window.PRODUCTOS_RESPALDO = {texto};\n", encoding="utf-8")
    print(f"Listo: {len(productos)} celulares, TODOS con fotos reales, de {len(marcas)} marcas.")


if __name__ == "__main__":
    main()
