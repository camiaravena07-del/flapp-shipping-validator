"""
Ejemplo de uso del cliente Flapp directamente (sin FastAPI)
"""

from flapp_client import FlappClient

# Inicializar cliente (lee credenciales de .env)
client = FlappClient()

# Ejemplo 1: Consultar un SKU
print("=" * 60)
print("Ejemplo 1: Consultar disponibilidad de un SKU")
print("=" * 60)

result = client.check_sku_availability(
    sku="ABC-001",
    phone="56912345678",
    address1="Av. Kennedy 4700",
    commune="vitacura",
    latitude=-33.4015,
    longitude=-70.5866,
    quantity=1,
    price=12990.0,
)

print(f"\nSKU: ABC-001")
print(f"Disponible: {result['available']}")
print(f"Error: {result['error']}")
print(f"Status Code: {result['status_code']}")

if result["available"]:
    print(f"\nTarifas disponibles ({len(result['rates'])} opciones):")
    for rate in result["rates"]:
        print(f"  - {rate.get('title')}: ${rate.get('price')} | ETA: {rate.get('eta')}")
else:
    print("No hay tarifas disponibles en esta dirección")

# Ejemplo 2: Consultar múltiples SKUs
print("\n" + "=" * 60)
print("Ejemplo 2: Consultar múltiples SKUs (batch)")
print("=" * 60)

skus_to_check = ["ABC-001", "ABC-002", "ABC-003"]

results = client.batch_check_skus(
    skus=skus_to_check,
    phone="56912345678",
    address1="Av. Kennedy 4700",
    commune="vitacura",
    latitude=-33.4015,
    longitude=-70.5866,
)

print(f"\nConsultando {len(skus_to_check)} SKUs...")
for sku, result in results.items():
    status = "✓ Disponible" if result["available"] else "✗ No disponible"
    error = f" (Error: {result['error']})" if result["error"] else ""
    print(f"  {sku}: {status}{error}")

# Ejemplo 3: Mostrar estructura completa de una respuesta
print("\n" + "=" * 60)
print("Ejemplo 3: Respuesta completa (raw)")
print("=" * 60)

result = client.check_sku_availability(
    sku="ABC-001",
    phone="56912345678",
    address1="Av. Kennedy 4700",
    commune="vitacura",
    latitude=-33.4015,
    longitude=-70.5866,
)

import json

print("\nRespuesta completa de Flapp:")
print(json.dumps(result["raw_response"], indent=2))
