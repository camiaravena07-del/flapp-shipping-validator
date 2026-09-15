"""
API FastAPI para validar disponibilidad de Flapp
Widget frontend llama a: GET /api/check-availability?sku=ABC-001&address=Av.%20Kennedy&commune=vitacura&lat=-33.4015&lon=-70.5866
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from flapp_client import FlappClient

app = FastAPI(
    title="Flapp Shipping Validator",
    description="API para validar disponibilidad de despacho con Flapp",
    version="1.0.0",
)

# Habilitar CORS para que el frontend de Magento pueda llamar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar los dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar cliente Flapp
flapp_client = FlappClient()


class CheckAvailabilityRequest(BaseModel):
    """Modelo para POST /api/check-availability"""

    sku: str
    phone: str = "56912345678"  # Default, el frontend debería pasarlo
    address1: str
    commune: str
    latitude: float
    longitude: float
    quantity: int = 1
    price: float = 10000.0


class AvailabilityResponse(BaseModel):
    """Respuesta de disponibilidad"""

    sku: str
    available: bool
    rates: List[dict] = []
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok"}


@app.get("/api/check-availability", response_model=AvailabilityResponse)
async def check_availability_get(
    sku: str = Query(..., description="SKU del producto"),
    phone: str = Query("56912345678", description="Teléfono del cliente"),
    address1: str = Query(..., description="Dirección principal"),
    commune: str = Query(..., description="Comuna destino"),
    lat: float = Query(..., description="Latitud", alias="latitude"),
    lon: float = Query(..., description="Longitud", alias="longitude"),
    quantity: int = Query(1, description="Cantidad"),
    price: float = Query(10000.0, description="Precio unitario"),
):
    """
    Valida disponibilidad de un SKU en una dirección

    Ejemplo:
    GET /api/check-availability?sku=ABC-001&address1=Av.%20Kennedy%204700&commune=vitacura&lat=-33.4015&lon=-70.5866&phone=56912345678

    Respuesta:
    {
      "sku": "ABC-001",
      "available": true,
      "rates": [
        {
          "id": 482910,
          "title": "Envío Express ⚡",
          "price": 3990,
          "eta": "2026-05-07T16:30:00Z"
        }
      ],
      "error": null
    }
    """
    try:
        result = flapp_client.check_sku_availability(
            sku=sku,
            phone=phone,
            address1=address1,
            commune=commune,
            latitude=lat,
            longitude=lon,
            quantity=quantity,
            price=price,
        )

        return AvailabilityResponse(
            sku=sku,
            available=result["available"],
            rates=result["rates"],
            error=result["error"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/check-availability", response_model=AvailabilityResponse)
async def check_availability_post(request: CheckAvailabilityRequest):
    """
    POST alternativo para validar disponibilidad

    Body:
    {
      "sku": "ABC-001",
      "phone": "56912345678",
      "address1": "Av. Kennedy 4700",
      "commune": "vitacura",
      "latitude": -33.4015,
      "longitude": -70.5866
    }
    """
    try:
        result = flapp_client.check_sku_availability(
            sku=request.sku,
            phone=request.phone,
            address1=request.address1,
            commune=request.commune,
            latitude=request.latitude,
            longitude=request.longitude,
            quantity=request.quantity,
            price=request.price,
        )

        return AvailabilityResponse(
            sku=request.sku,
            available=result["available"],
            rates=result["rates"],
            error=result["error"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch-check")
async def batch_check(skus: List[str], phone: str, address1: str, commune: str, latitude: float, longitude: float):
    """
    Valida múltiples SKUs de una sola vez

    Body:
    {
      "skus": ["ABC-001", "ABC-002"],
      "phone": "56912345678",
      "address1": "Av. Kennedy 4700",
      "commune": "vitacura",
      "latitude": -33.4015,
      "longitude": -70.5866
    }

    Respuesta:
    {
      "ABC-001": {"available": true, "rates": [...], "error": null},
      "ABC-002": {"available": false, "rates": [], "error": null}
    }
    """
    try:
        results = flapp_client.batch_check_skus(
            skus=skus,
            phone=phone,
            address1=address1,
            commune=commune,
            latitude=latitude,
            longitude=longitude,
        )

        # Transformar respuesta
        formatted_results = {}
        for sku, result in results.items():
            formatted_results[sku] = {
                "available": result["available"],
                "rates": result["rates"],
                "error": result["error"],
            }

        return formatted_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
