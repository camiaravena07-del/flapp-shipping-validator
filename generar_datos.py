"""
Genera datos.json con la disponibilidad de despacho Flapp por comuna.

Este script corre en GitHub Actions (no en tu computador).
Lee el feed de productos, consulta la API de Flapp para cada SKU en cada
comuna, y guarda el resultado en datos.json para que lo lea el dashboard.

Para probarlo sin gastar llamadas a la API:
    python generar_datos.py --demo
"""

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

from flapp_client import FlappClient

# ---------------------------------------------------------------------------
# CONFIGURACION - esto es lo unico que necesitas tocar
# ---------------------------------------------------------------------------

FEED_URL = "https://resources.komaxchile.cl/google-feeds/the-north-face-cl-google-feed.xml"
MARCA = "The North Face"

# Cuantos SKUs revisar. Empieza chico para validar que todo funciona.
# OJO: el total de llamadas a Flapp es MAX_SKUS x cantidad de comunas.
#      40 SKUs x 52 comunas = 2.080 llamadas (~3 minutos)
#      500 SKUs x 52 comunas = 26.000 llamadas (~35 minutos)
MAX_SKUS = 40

# Solo revisar productos que el feed marca con stock. Un producto sin stock
# nunca va a tener despacho, asi que consultarlo es gastar llamadas al pedo.
SOLO_CON_STOCK = True

# Cuantas consultas en paralelo. Subirlo acelera pero puede gatillar rate
# limiting en Flapp. 8 es un punto seguro.
CONCURRENCIA = 8

# Datos de contacto ficticios que la API exige. No afectan el resultado:
# lo que define la cobertura es la latitud/longitud.
TELEFONO = "56912345678"
DIRECCION = "Avenida Principal 100"

# Las 52 comunas de la Region Metropolitana con su centroide aproximado.
# Para sacar una comuna de la consulta, comenta la linea con #
COMUNAS = {
    "Santiago": (-33.4489, -70.6693),
    "Providencia": (-33.4314, -70.6093),
    "Las Condes": (-33.4088, -70.5677),
    "Vitacura": (-33.3897, -70.5760),
    "Lo Barnechea": (-33.3500, -70.5167),
    "Nunoa": (-33.4569, -70.5975),
    "La Reina": (-33.4450, -70.5400),
    "Penalolen": (-33.4850, -70.5400),
    "Macul": (-33.4900, -70.5980),
    "San Joaquin": (-33.4950, -70.6300),
    "La Florida": (-33.5220, -70.5990),
    "Puente Alto": (-33.6110, -70.5760),
    "San Bernardo": (-33.5920, -70.7000),
    "Maipu": (-33.5110, -70.7580),
    "Pudahuel": (-33.4400, -70.7500),
    "Cerrillos": (-33.4950, -70.7150),
    "Estacion Central": (-33.4600, -70.6900),
    "Quinta Normal": (-33.4300, -70.7000),
    "Lo Prado": (-33.4450, -70.7300),
    "Cerro Navia": (-33.4230, -70.7400),
    "Renca": (-33.4030, -70.7280),
    "Quilicura": (-33.3670, -70.7290),
    "Huechuraba": (-33.3700, -70.6450),
    "Conchali": (-33.3850, -70.6750),
    "Independencia": (-33.4150, -70.6650),
    "Recoleta": (-33.4100, -70.6400),
    "Pedro Aguirre Cerda": (-33.4900, -70.6700),
    "San Miguel": (-33.4950, -70.6520),
    "Lo Espejo": (-33.5200, -70.6900),
    "La Cisterna": (-33.5300, -70.6620),
    "El Bosque": (-33.5600, -70.6750),
    "La Granja": (-33.5400, -70.6250),
    "San Ramon": (-33.5400, -70.6450),
    "La Pintana": (-33.5830, -70.6330),
    "Colina": (-33.2020, -70.6750),
    "Lampa": (-33.2840, -70.8760),
    "Tiltil": (-33.0870, -70.9280),
    "Buin": (-33.7330, -70.7420),
    "Paine": (-33.8080, -70.7420),
    "Calera de Tango": (-33.6300, -70.7800),
    "Melipilla": (-33.6880, -71.2150),
    "Talagante": (-33.6640, -70.9280),
    "Penaflor": (-33.6100, -70.8790),
    "Padre Hurtado": (-33.5730, -70.8150),
    "El Monte": (-33.6780, -71.0110),
    "Isla de Maipo": (-33.7440, -70.8990),
    "Curacavi": (-33.4030, -71.1400),
    "Maria Pinto": (-33.5170, -71.1330),
    "San Pedro": (-33.8970, -71.4580),
    "Alhue": (-34.0300, -71.1000),
    "Pirque": (-33.6400, -70.5900),
    "San Jose de Maipo": (-33.6400, -70.3500),
}

NS = {"g": "http://base.google.com/ns/1.0"}
ARCHIVO_SALIDA = "datos.json"


# ---------------------------------------------------------------------------
# Lectura del feed
# ---------------------------------------------------------------------------

def _texto(item, *rutas):
    """Devuelve el texto del primer tag que exista. Maneja CDATA solo."""
    for ruta in rutas:
        nodo = item.find(ruta, NS)
        if nodo is not None and nodo.text:
            return nodo.text.strip()
    return ""


def leer_feed(url):
    """Descarga el feed XML y devuelve la lista de productos."""
    print(f"Descargando feed: {url}")
    respuesta = requests.get(url, timeout=120)
    respuesta.raise_for_status()

    raiz = ET.fromstring(respuesta.content)
    items = raiz.findall(".//item")
    print(f"El feed trae {len(items)} productos en total.")

    productos = []
    for item in items:
        # OJO: el titulo viene en <title>, NO en <g:title>.
        # El link tambien viene en <link> sin prefijo.
        sku = _texto(item, "g:id")
        if not sku:
            continue

        disponibilidad = _texto(item, "g:availability").lower()
        cantidad_txt = _texto(item, "g:qty")
        try:
            cantidad = int(cantidad_txt) if cantidad_txt else 0
        except ValueError:
            cantidad = 0

        con_stock = "in stock" in disponibilidad and cantidad > 0

        productos.append({
            "sku": sku,
            "titulo": _texto(item, "title", "g:title") or sku,
            "precio": _texto(item, "g:sale_price") or _texto(item, "g:price"),
            "precio_lista": _texto(item, "g:price"),
            "imagen": _texto(item, "g:image_link"),
            "link": _texto(item, "link", "g:link"),
            "categoria": _texto(item, "g:pmax"),
            "color": _texto(item, "g:color"),
            "genero": _texto(item, "g:genero"),
            "stock": cantidad,
            "con_stock": con_stock,
        })

    return productos


def filtrar(productos):
    """Aplica el filtro de stock y el tope de SKUs."""
    seleccion = productos
    if SOLO_CON_STOCK:
        seleccion = [p for p in seleccion if p["con_stock"]]
        print(f"Con stock disponible: {len(seleccion)}")

    if MAX_SKUS and len(seleccion) > MAX_SKUS:
        # Prioriza los que tienen mas stock: son los que mas importa saber.
        seleccion = sorted(seleccion, key=lambda p: -p["stock"])[:MAX_SKUS]
        print(f"Limitado a los {MAX_SKUS} con mas stock (MAX_SKUS).")

    return seleccion


# ---------------------------------------------------------------------------
# Consulta a Flapp
# ---------------------------------------------------------------------------

def consultar(cliente, sku, comuna, lat, lon):
    """Una consulta. Devuelve (comuna, sku, disponible, tarifa_min, error)."""
    try:
        r = cliente.check_sku_availability(
            sku=sku,
            phone=TELEFONO,
            address1=DIRECCION,
            commune=comuna,
            latitude=lat,
            longitude=lon,
        )
    except Exception as e:  # noqa: BLE001 - nunca queremos que muera el batch
        return comuna, sku, False, None, str(e)

    tarifas = r.get("rates") or []
    tarifa_min = None
    if tarifas:
        precios = []
        for t in tarifas:
            for clave in ("price", "amount", "total", "value"):
                if isinstance(t.get(clave), (int, float)):
                    precios.append(t[clave])
                    break
        if precios:
            tarifa_min = min(precios)

    return comuna, sku, bool(r.get("available")), tarifa_min, r.get("error")


def recorrer_todo(productos):
    """Consulta cada SKU en cada comuna, en paralelo."""
    cliente = FlappClient(env=os.getenv("FLAPP_ENV", "production"))

    trabajos = [
        (p["sku"], comuna, lat, lon)
        for comuna, (lat, lon) in COMUNAS.items()
        for p in productos
    ]
    total = len(trabajos)
    print(f"\n{len(productos)} SKUs x {len(COMUNAS)} comunas = {total} consultas")
    print(f"Concurrencia: {CONCURRENCIA}\n")

    resultado = {
        comuna: {"disponibles": [], "no_disponibles": [], "errores": [], "tarifas": {}}
        for comuna in COMUNAS
    }

    inicio = time.time()
    hechas = 0
    fallidas = 0

    with ThreadPoolExecutor(max_workers=CONCURRENCIA) as pool:
        futuros = [
            pool.submit(consultar, cliente, sku, comuna, lat, lon)
            for sku, comuna, lat, lon in trabajos
        ]
        for futuro in as_completed(futuros):
            comuna, sku, disponible, tarifa_min, error = futuro.result()
            bloque = resultado[comuna]

            if error:
                fallidas += 1
                bloque["errores"].append(sku)
            elif disponible:
                bloque["disponibles"].append(sku)
                if tarifa_min is not None:
                    bloque["tarifas"][sku] = tarifa_min
            else:
                bloque["no_disponibles"].append(sku)

            hechas += 1
            if hechas % 200 == 0 or hechas == total:
                transcurrido = time.time() - inicio
                ritmo = hechas / transcurrido if transcurrido else 0
                faltan = (total - hechas) / ritmo if ritmo else 0
                print(
                    f"  {hechas}/{total} consultas "
                    f"({ritmo:.1f}/s, faltan ~{faltan/60:.1f} min, "
                    f"{fallidas} con error)"
                )

    print(f"\nListo en {(time.time() - inicio)/60:.1f} minutos.")
    if fallidas:
        print(f"ATENCION: {fallidas} consultas fallaron y quedaron marcadas como error.")

    for bloque in resultado.values():
        bloque["disponibles"].sort()
        bloque["no_disponibles"].sort()
        bloque["errores"].sort()

    return resultado


def recorrer_demo(productos):
    """Modo demo: inventa resultados para probar el dashboard sin llamar a Flapp."""
    import random

    random.seed(42)
    print("\nMODO DEMO: no se llama a Flapp, los datos son inventados.\n")

    resultado = {}
    for indice, comuna in enumerate(COMUNAS):
        # Las comunas del centro/oriente con mas cobertura que las rurales.
        cobertura = 0.9 if indice < 20 else (0.5 if indice < 34 else 0.15)
        bloque = {"disponibles": [], "no_disponibles": [], "errores": [], "tarifas": {}}
        for p in productos:
            if random.random() < cobertura:
                bloque["disponibles"].append(p["sku"])
                bloque["tarifas"][p["sku"]] = random.choice([2990, 3490, 4990, 5990])
            else:
                bloque["no_disponibles"].append(p["sku"])
        resultado[comuna] = bloque
    return resultado


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Genera datos inventados para probar el dashboard sin llamar a Flapp",
    )
    args = parser.parse_args()

    productos = leer_feed(FEED_URL)
    if not productos:
        print("ERROR: el feed no devolvio ningun producto.")
        sys.exit(1)

    seleccion = filtrar(productos)
    if not seleccion:
        print("ERROR: ningun producto paso el filtro.")
        sys.exit(1)

    if args.demo:
        por_comuna = recorrer_demo(seleccion)
    else:
        por_comuna = recorrer_todo(seleccion)

    salida = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "marca": MARCA,
        "feed": FEED_URL,
        "es_demo": args.demo,
        "total_skus": len(seleccion),
        "total_comunas": len(COMUNAS),
        "productos": {
            p["sku"]: {
                "titulo": p["titulo"],
                "precio": p["precio"],
                "imagen": p["imagen"],
                "link": p["link"],
                "categoria": p["categoria"],
                "color": p["color"],
                "genero": p["genero"],
                "stock": p["stock"],
            }
            for p in seleccion
        },
        "comunas": por_comuna,
    }

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))

    peso = os.path.getsize(ARCHIVO_SALIDA) / 1024
    print(f"\nEscrito {ARCHIVO_SALIDA} ({peso:.0f} KB)")

    print("\nCobertura por comuna:")
    for comuna, bloque in sorted(
        por_comuna.items(), key=lambda x: -len(x[1]["disponibles"])
    ):
        n = len(bloque["disponibles"])
        pct = n / len(seleccion) * 100 if seleccion else 0
        print(f"  {comuna:<24} {n:>4}/{len(seleccion)}  ({pct:.0f}%)")


if __name__ == "__main__":
    main()
