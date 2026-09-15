# Flapp Shipping Validator

Endpoint Python/FastAPI para validar qué productos (SKUs) tienen disponibilidad de despacho con Flapp.

## Propósito

Mostrar en el sitio de Grupo Axo (~600 productos) cuáles tienen disponible el servicio de envío con Flapp. El widget frontend consulta este endpoint en tiempo real.

## Estructura

```
flapp-shipping-validator/
├── main.py              # API FastAPI
├── flapp_client.py      # Cliente que consulta Flapp API
├── test_flapp_client.py # Tests del cliente
├── test_api.py          # Tests de la API
├── requirements.txt     # Dependencias
├── .env.example         # Plantilla de variables
├── .gitignore           # Git ignore
└── README.md            # Este archivo
```

## Setup Local

### 1. Clonar y instalar

```bash
git clone <tu-repo> flapp-shipping-validator
cd flapp-shipping-validator

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar credenciales de Flapp

```bash
# Copiar plantilla
cp .env.example .env

# Editar .env con tus credenciales
# FLAPP_API_KEY=tu_api_key_aqui
# FLAPP_API_SECRET=tu_api_secret_aqui
# FLAPP_ENV=sandbox  # O production
```

### 3. Correr tests

```bash
# Tests del cliente Flapp
pytest test_flapp_client.py -v

# Tests de la API
pytest test_api.py -v

# Todos los tests
pytest -v
```

### 4. Iniciar servidor

```bash
# En desarrollo
python main.py

# O con uvicorn directamente
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará en: `http://localhost:8000`

Swagger docs: `http://localhost:8000/docs`

## Endpoints

### GET /api/check-availability

Valida disponibilidad de un SKU en una dirección.

**Query Parameters:**
- `sku` (string, required): SKU del producto. Ej: `ABC-001`
- `phone` (string, default: `56912345678`): Teléfono del cliente. Ej: `56912345678`
- `address1` (string, required): Dirección. Ej: `Av. Kennedy 4700`
- `commune` (string, required): Comuna. Ej: `vitacura`
- `latitude` (float, required): Latitud. Ej: `-33.4015`
- `longitude` (float, required): Longitud. Ej: `-70.5866`
- `quantity` (int, default: `1`): Cantidad
- `price` (float, default: `10000.0`): Precio unitario

**Ejemplo:**

```bash
curl "http://localhost:8000/api/check-availability?sku=ABC-001&address1=Av.%20Kennedy%204700&commune=vitacura&lat=-33.4015&lon=-70.5866&phone=56912345678"
```

**Respuesta:**

```json
{
  "sku": "ABC-001",
  "available": true,
  "rates": [
    {
      "id": 482910,
      "title": "Envío Express ⚡",
      "code": "Flapp rates ONE-REG-NOSC...",
      "description": "Llegada hoy antes de las 16:30.",
      "price": 3990,
      "shippingType": "express",
      "eta": "2026-05-07T16:30:00Z"
    },
    {
      "id": 482911,
      "title": "Despacho same day",
      "code": "Flapp rates ONE-REG-NOSC...",
      "description": "Llega hoy",
      "price": 2990,
      "shippingType": "courier",
      "eta": "2026-05-07T20:00:00Z"
    }
  ],
  "error": null
}
```

### POST /api/check-availability

Alternativa POST para validar disponibilidad.

**Body JSON:**

```json
{
  "sku": "ABC-001",
  "phone": "56912345678",
  "address1": "Av. Kennedy 4700",
  "commune": "vitacura",
  "latitude": -33.4015,
  "longitude": -70.5866,
  "quantity": 1,
  "price": 10000.0
}
```

**Ejemplo:**

```bash
curl -X POST http://localhost:8000/api/check-availability \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "ABC-001",
    "phone": "56912345678",
    "address1": "Av. Kennedy 4700",
    "commune": "vitacura",
    "latitude": -33.4015,
    "longitude": -70.5866
  }'
```

### POST /api/batch-check

Valida múltiples SKUs de una sola vez.

**Body JSON:**

```json
{
  "skus": ["ABC-001", "ABC-002", "ABC-003"],
  "phone": "56912345678",
  "address1": "Av. Kennedy 4700",
  "commune": "vitacura",
  "latitude": -33.4015,
  "longitude": -70.5866
}
```

**Respuesta:**

```json
{
  "ABC-001": {
    "available": true,
    "rates": [
      {
        "id": 482910,
        "title": "Envío Express ⚡",
        "price": 3990
      }
    ],
    "error": null
  },
  "ABC-002": {
    "available": false,
    "rates": [],
    "error": null
  },
  "ABC-003": {
    "available": true,
    "rates": [
      {
        "id": 482911,
        "title": "Despacho same day",
        "price": 2990
      }
    ],
    "error": null
  }
}
```

## Integración en Magento

### Opción 1: Widget en Frontend (recomendado)

En tu página de producto Magento, agrega un widget que:

1. Obtiene la dirección del cliente (de su sesión o formulario)
2. Consulta `GET /api/check-availability?sku=...&address1=...&commune=...&lat=...&lon=...`
3. Muestra un badge o banner si hay disponibilidad Flapp

**Pseudocódigo JavaScript:**

```javascript
// En la página de producto
const sku = document.querySelector('[data-sku]').dataset.sku;
const customerAddress = getCurrentCustomerAddress(); // De Magento

fetch(`http://tu-server/api/check-availability?sku=${sku}&address1=${customerAddress.street}&commune=${customerAddress.commune}&lat=${customerAddress.lat}&lon=${customerAddress.lon}`)
  .then(res => res.json())
  .then(data => {
    if (data.available) {
      // Mostrar "Envío con Flapp disponible"
      // Mostrar tarifas en data.rates
      showFlappWidget(data.rates);
    }
  });
```

### Opción 2: Precompute (más rápido pero menos actualizado)

Cron job que ejecuta batch-check cada noche y guarda disponibilidad en una tabla custom de Magento.

```python
# Pseudocódigo
for brand in brands:
    skus = get_all_skus_for_brand(brand)
    response = POST /api/batch-check with default_address for brand
    save_to_magento_custom_table(response)
```

## Variables de Entorno

```bash
# Credenciales Flapp (obtén del equipo Flapp/Vicente Barros)
FLAPP_API_KEY=xxx
FLAPP_API_SECRET=yyy

# Ambiente
FLAPP_ENV=sandbox  # sandbox o production
```

## Obtener Credenciales de Flapp

1. Contacta al partner de Flapp: **Vicente Barros**
2. Solicita:
   - API Key (para sandbox)
   - API Secret (para sandbox)
   - Confirmación de que tu cuenta está lista en Flapp
3. Configura en `.env`

## Testing

### Tests unitarios (sin Flapp)

```bash
pytest -v
```

Todos los tests usan mocks, no requieren credenciales reales.

### Testing manual con Flapp real

Una vez tengas credenciales, prueba:

```bash
# Editar .env con tus credenciales reales
# Luego correr el servidor
python main.py

# En otra terminal, consultar
curl "http://localhost:8000/api/check-availability?sku=TU_SKU_REAL&address1=Av.%20Kennedy%204700&commune=vitacura&lat=-33.4015&lon=-70.5866"
```

## HMAC-SHA256 Signature

El cliente maneja automáticamente la firma que Flapp requiere. Si modificas `flapp_client.py`, recuerda:

1. JSON debe ser **minificado** (sin espacios): `json.dumps(payload, separators=(",", ":"))`
2. Firma se calcula sobre el body crudo
3. Encoding: UTF-8 → base64 estándar (con padding)

Vector de prueba de Flapp:
- `apiSecret`: `test-secret`
- `rawBody`: `{"hello":"world"}`
- `Expected HMAC-SHA256`: `hMwz33Fu0LBZjwdDfJQGms43MDWHeKWSvWu9FCPREfM=`

Verifica en test: `test_hmac_generation()`

## Próximos Pasos

1. ✅ Validar en GitHub (este repo)
2. ⬜ Obtener credenciales Flapp de Vicente Barros
3. ⬜ Testear con SKUs reales en sandbox de Flapp
4. ⬜ Integrar widget en Magento (frontend)
5. ⬜ Deploy a producción (cuando Flapp esté listo)
6. ⬜ Monitorear errores y latencia

## Troubleshooting

**Error 403 Forbidden**
- Verifica FLAPP_API_KEY y FLAPP_API_SECRET en .env
- Verifica que la firma HMAC es correcta (revisa logs)

**Error: SKU no encontrado**
- El SKU no ha sido sincronizado a Flapp aún
- Revisa que POST /sqs/integrations/generic/process-product haya enviado el SKU

**Timeout (>10s)**
- Flapp puede estar lento
- Verifica tu conexión a internet
- Revisa el status de Flapp

**"rates" vacío pero "error" null**
- No hay cobertura Flapp en esa dirección
- Es normal en zonas remotas

## Licencia

MIT

## Contacto

Cami - caravena@grupoaxo.com
