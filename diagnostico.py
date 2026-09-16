"""
Diagnostico: por que Flapp devuelve la lista de tarifas vacia.

Prueba combinaciones de ambiente, SKU, comuna y direccion, y muestra la
respuesta CRUDA de Flapp en cada caso. Es de un solo uso: cuando sepamos
cual es el formato correcto, este archivo se borra.

Corre desde GitHub Actions con el workflow "Diagnostico Flapp".
"""

import json
import os
import xml.etree.ElementTree as ET

import requests

from flapp_client import FlappClient

FEED_URL = "https://resources.komaxchile.cl/google-feeds/the-north-face-cl-google-feed.xml"
NS = {"g": "http://base.google.com/ns/1.0"}

# Valores exactos del ejemplo documentado en el README.
# Direccion real, comuna en minuscula, coordenadas de esa direccion.
REF_DIRECCION = "Av. Kennedy 4700"
REF_COMUNA = "vitacura"
REF_LAT = -33.4015
REF_LON = -70.5866
REF_TELEFONO = "56912345678"

raya = "=" * 72


def primeros_skus(n=3):
    """Saca los primeros SKUs con stock del feed."""
    r = requests.get(FEED_URL, timeout=120)
    r.raise_for_status()
    raiz = ET.fromstring(r.content)

    encontrados = []
    for item in raiz.findall(".//item"):
        gid = item.find("g:id", NS)
        qty = item.find("g:qty", NS)
        disp = item.find("g:availability", NS)
        if gid is None or not gid.text:
            continue
        cantidad = int(qty.text) if (qty is not None and qty.text and qty.text.isdigit()) else 0
        en_stock = disp is not None and disp.text and "in stock" in disp.text.lower()
        if cantidad > 0 and en_stock:
            encontrados.append((gid.text.strip(), cantidad))
        if len(encontrados) >= n:
            break
    return encontrados


def variantes_sku(sku):
    """El feed entrega NF00A1KS_NFKX7. La URL del producto usa guion medio.
    Probamos las formas mas plausibles del SKU real en Magento."""
    formas = [("feed tal cual", sku)]
    if "_" in sku:
        formas.append(("guion medio", sku.replace("_", "-")))
        formas.append(("solo modelo", sku.split("_")[0]))
        formas.append(("sin separador", sku.replace("_", "")))
    return formas


def probar(cliente, etiqueta, **kw):
    """Hace una consulta y muestra la respuesta cruda completa."""
    try:
        r = cliente.check_sku_availability(**kw)
    except Exception as e:  # noqa: BLE001
        print(f"  [{etiqueta}] EXCEPCION: {e}")
        return False

    cod = r.get("status_code")
    tarifas = r.get("rates") or []
    marca = "SI HAY TARIFAS" if tarifas else "vacio"
    print(f"  [{etiqueta}] HTTP {cod} -> {marca} ({len(tarifas)} tarifas)")

    if r.get("error"):
        print(f"      error: {r['error']}")

    cruda = r.get("raw_response")
    if cruda is not None:
        texto = json.dumps(cruda, ensure_ascii=False) if isinstance(cruda, (dict, list)) else str(cruda)
        if len(texto) > 900:
            texto = texto[:900] + " ...(cortado)"
        print(f"      respuesta: {texto}")

    return bool(tarifas)


def main():
    clave = os.getenv("FLAPP_API_KEY", "")
    secreto = os.getenv("FLAPP_API_SECRET", "")
    print(raya)
    print("CREDENCIALES")
    print(raya)
    print(f"API key    : {'presente' if clave else 'FALTA'} "
          f"(largo {len(clave)}, empieza en {clave[:6]}...)")
    print(f"API secret : {'presente' if secreto else 'FALTA'} (largo {len(secreto)})")

    skus = primeros_skus(3)
    print(f"\nSKUs del feed con stock: {skus}")
    if not skus:
        print("El feed no devolvio SKUs con stock. Nada mas que probar.")
        return

    sku_base = skus[0][0]
    exito = False

    # ---------------------------------------------------------------
    # PRUEBA 1 - Direccion y comuna exactas del README, variando el SKU
    #            y el ambiente. Aisla si el problema es el SKU.
    # ---------------------------------------------------------------
    for ambiente in ("production", "sandbox"):
        print(f"\n{raya}")
        print(f"PRUEBA 1 - ambiente '{ambiente}', direccion y comuna del README")
        print(f"  direccion: {REF_DIRECCION}, comuna: {REF_COMUNA}, "
              f"lat/lon: {REF_LAT}/{REF_LON}")
        print(raya)
        try:
            cliente = FlappClient(env=ambiente)
        except Exception as e:  # noqa: BLE001
            print(f"  No se pudo crear el cliente: {e}")
            continue
        print(f"  URL base: {cliente.base_url}")

        for sku_real, _stock in skus[:2]:
            print(f"\n  SKU del feed: {sku_real}")
            for nombre, variante in variantes_sku(sku_real):
                ok = probar(
                    cliente, f"{nombre}: {variante}",
                    sku=variante, phone=REF_TELEFONO, address1=REF_DIRECCION,
                    commune=REF_COMUNA, latitude=REF_LAT, longitude=REF_LON,
                )
                exito = exito or ok

    # ---------------------------------------------------------------
    # PRUEBA 2 - Formato del nombre de comuna
    # ---------------------------------------------------------------
    print(f"\n{raya}")
    print("PRUEBA 2 - formato del nombre de comuna (ambiente production)")
    print(raya)
    try:
        cliente = FlappClient(env="production")
        for etiqueta, comuna in [
            ("minuscula", "vitacura"),
            ("capitalizada", "Vitacura"),
            ("mayuscula", "VITACURA"),
            ("dos palabras con espacio", "las condes"),
            ("dos palabras capitalizadas", "Las Condes"),
            ("dos palabras guion bajo", "las_condes"),
        ]:
            lat, lon = (REF_LAT, REF_LON) if "condes" not in comuna.lower() else (-33.4088, -70.5677)
            ok = probar(
                cliente, f"{etiqueta}: '{comuna}'",
                sku=sku_base, phone=REF_TELEFONO, address1=REF_DIRECCION,
                commune=comuna, latitude=lat, longitude=lon,
            )
            exito = exito or ok
    except Exception as e:  # noqa: BLE001
        print(f"  No se pudo probar: {e}")

    # ---------------------------------------------------------------
    # PRUEBA 3 - Importa la calle, o basta con lat/lon?
    # ---------------------------------------------------------------
    print(f"\n{raya}")
    print("PRUEBA 3 - direccion real vs inventada (ambiente production)")
    print(raya)
    try:
        cliente = FlappClient(env="production")
        for etiqueta, direccion in [
            ("real del README", REF_DIRECCION),
            ("inventada (la que uso el script)", "Avenida Principal 100"),
            ("vacia", ""),
        ]:
            ok = probar(
                cliente, f"{etiqueta}: '{direccion}'",
                sku=sku_base, phone=REF_TELEFONO, address1=direccion,
                commune=REF_COMUNA, latitude=REF_LAT, longitude=REF_LON,
            )
            exito = exito or ok
    except Exception as e:  # noqa: BLE001
        print(f"  No se pudo probar: {e}")

    # ---------------------------------------------------------------
    print(f"\n{raya}")
    print("CONCLUSION")
    print(raya)
    if exito:
        print("Al menos una combinacion devolvio tarifas.")
        print("Busca arriba las lineas que dicen 'SI HAY TARIFAS': ese es el")
        print("formato correcto, y con eso ajustamos generar_datos.py.")
    else:
        print("Ninguna combinacion devolvio tarifas, y no hubo errores HTTP.")
        print("Flapp responde bien pero no conoce estos productos.")
        print("Lo mas probable es que los SKUs de The North Face no esten")
        print("sincronizados a Flapp todavia (POST process-product).")
        print("Eso se resuelve con Flapp, no desde este repo.")


if __name__ == "__main__":
    main()
