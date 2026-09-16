"""
Diagnostico v2: probar bodegas (stockSourceIds) y SKU con talla.

Hipotesis que dejo la ronda anterior:
  1. Flapp maneja el SKU a nivel de talla (NF0A8FBC_NF173_S), no el
     padre que trae el feed (NF0A8FBC_NF173).
  2. delivery-rates necesita saber la bodega de origen (1002, 1069, 1010).

Este script prueba cada una por separado y despues juntas, para saber
cual de las dos pesa. Muestra la respuesta cruda de Flapp siempre.
"""

import json
import os
import xml.etree.ElementTree as ET

import requests

from flapp_client import FlappClient

FEED_URL = "https://resources.komaxchile.cl/google-feeds/the-north-face-cl-google-feed.xml"
NS = {"g": "http://base.google.com/ns/1.0"}

# Direccion de referencia (la del README, direccion real)
DIRECCION = "Av. Kennedy 4700"
COMUNA = "vitacura"
LAT = -33.4015
LON = -70.5866
TELEFONO = "56912345678"

# Las tres bodegas que maneja Grupo Axo
BODEGAS = ["1002", "1069", "1010"]

# Tallas a probar. Letras para ropa, numeros para calzado.
TALLAS_ROPA = ["XS", "S", "M", "L", "XL", "XXL", "U"]
TALLAS_CALZADO = ["7", "8", "9", "10", "40", "41", "42"]

CAT_ROPA = ("CHAQUETA", "POLERON", "POLERA", "PANTALON", "PARKA", "CORTAVIENTO")
CAT_CALZADO = ("BOTA", "ZAPATILLA", "CALZADO", "SANDALIA")

raya = "=" * 74
aciertos = []


def leer_feed():
    r = requests.get(FEED_URL, timeout=120)
    r.raise_for_status()
    raiz = ET.fromstring(r.content)

    productos = []
    for item in raiz.findall(".//item"):
        gid = item.find("g:id", NS)
        qty = item.find("g:qty", NS)
        cat = item.find("g:pmax", NS)
        tit = item.find("title", NS)
        if gid is None or not gid.text:
            continue
        cantidad = int(qty.text) if (qty is not None and qty.text and qty.text.isdigit()) else 0
        if cantidad <= 0:
            continue
        productos.append({
            "sku": gid.text.strip(),
            "stock": cantidad,
            "categoria": (cat.text or "").strip().upper() if cat is not None and cat.text else "",
            "titulo": (tit.text or "").strip() if tit is not None and tit.text else "",
        })
    return productos


def elegir(productos):
    """Elige una prenda y un calzado, priorizando los de mas stock
    (mas probable que tengan varias tallas disponibles)."""
    orden = sorted(productos, key=lambda p: -p["stock"])
    ropa = next((p for p in orden if any(c in p["categoria"] for c in CAT_ROPA)), None)
    calzado = next((p for p in orden if any(c in p["categoria"] for c in CAT_CALZADO)), None)
    return ropa, calzado


def probar(cliente, etiqueta, mostrar_payload=False, **kw):
    try:
        r = cliente.check_sku_availability(**kw)
    except Exception as e:  # noqa: BLE001
        print(f"  [{etiqueta}] EXCEPCION: {e}")
        return False

    tarifas = r.get("rates") or []
    cod = r.get("status_code")

    if tarifas:
        print(f"  >>> [{etiqueta}] HTTP {cod} -- {len(tarifas)} TARIFAS <<<")
        for t in tarifas:
            print(f"        {t.get('title')} | ${t.get('price')} | {t.get('shippingType')}")
        aciertos.append(etiqueta)
    else:
        print(f"  [{etiqueta}] HTTP {cod} -> vacio")

    if r.get("error"):
        print(f"      error: {r['error']}")

    cruda = r.get("raw_response")
    if cruda is not None and not tarifas:
        texto = json.dumps(cruda, ensure_ascii=False) if isinstance(cruda, (dict, list)) else str(cruda)
        print(f"      respuesta: {texto[:300]}")

    if mostrar_payload:
        cuerpo = {
            "items": [{"sku": kw["sku"], "quantity": 1, "price": 10000.0}],
            "phone": kw["phone"],
            "shippingAddress": {
                "address1": kw["address1"], "commune": kw["commune"],
                "latitude": kw["latitude"], "longitude": kw["longitude"],
            },
        }
        if kw.get("stock_source_ids"):
            cuerpo["options"] = {"stockSourceIds": [
                {"stockSourceId": s} for s in kw["stock_source_ids"]]}
        print(f"      payload enviado: {json.dumps(cuerpo, ensure_ascii=False)}")

    return bool(tarifas)


def main():
    productos = leer_feed()
    ropa, calzado = elegir(productos)

    print(raya)
    print("PRODUCTOS ELEGIDOS")
    print(raya)
    for rotulo, p in (("ropa", ropa), ("calzado", calzado)):
        if p:
            print(f"  {rotulo:8} {p['sku']}  stock {p['stock']}  [{p['categoria']}]")
            print(f"           {p['titulo']}")
        else:
            print(f"  {rotulo:8} no se encontro ninguno en el feed")

    base = (ropa or calzado)
    if not base:
        print("\nEl feed no devolvio productos utilizables.")
        return
    sku_base = base["sku"]

    cliente = FlappClient(env="production")
    print(f"\n  URL base: {cliente.base_url}")
    print(f"  Direccion: {DIRECCION}, {COMUNA} ({LAT}, {LON})")

    # -----------------------------------------------------------------
    print(f"\n{raya}")
    print("PRUEBA A - bodegas, con el SKU padre tal cual viene del feed")
    print(f"  SKU: {sku_base}")
    print(raya)

    comun = dict(phone=TELEFONO, address1=DIRECCION, commune=COMUNA,
                 latitude=LAT, longitude=LON)

    probar(cliente, "sin bodegas (control)", sku=sku_base, **comun)
    probar(cliente, f"las 3 como texto {BODEGAS}", sku=sku_base,
           stock_source_ids=BODEGAS, mostrar_payload=True, **comun)
    probar(cliente, "las 3 como numero", sku=sku_base,
           stock_source_ids=[int(b) for b in BODEGAS], **comun)
    for bodega in BODEGAS:
        probar(cliente, f"solo bodega {bodega}", sku=sku_base,
               stock_source_ids=[bodega], **comun)

    # -----------------------------------------------------------------
    print(f"\n{raya}")
    print("PRUEBA B - SKU con talla, SIN bodegas")
    print(raya)

    for rotulo, p, tallas in (("ropa", ropa, TALLAS_ROPA),
                              ("calzado", calzado, TALLAS_CALZADO)):
        if not p:
            continue
        print(f"\n  {rotulo}: {p['sku']}")
        for talla in tallas:
            probar(cliente, f"{p['sku']}_{talla}", sku=f"{p['sku']}_{talla}", **comun)

    # -----------------------------------------------------------------
    print(f"\n{raya}")
    print("PRUEBA C - SKU con talla + las 3 bodegas (la combinacion completa)")
    print(raya)

    for rotulo, p, tallas in (("ropa", ropa, TALLAS_ROPA),
                              ("calzado", calzado, TALLAS_CALZADO)):
        if not p:
            continue
        print(f"\n  {rotulo}: {p['sku']}")
        for talla in tallas:
            probar(cliente, f"{p['sku']}_{talla} + bodegas",
                   sku=f"{p['sku']}_{talla}", stock_source_ids=BODEGAS, **comun)

    # -----------------------------------------------------------------
    print(f"\n{raya}")
    print("CONCLUSION")
    print(raya)
    if aciertos:
        print(f"{len(aciertos)} combinacion(es) devolvieron tarifas:\n")
        for a in aciertos:
            print(f"  - {a}")
        print("\nCon eso ajusto generar_datos.py al formato correcto.")
    else:
        print("Ninguna combinacion devolvio tarifas.")
        print("Ni la talla ni las bodegas explican el vacio.")
        print("Queda confirmar con Flapp si los productos de The North Face")
        print("estan cargados en la cuenta de Grupo Axo.")


if __name__ == "__main__":
    main()
