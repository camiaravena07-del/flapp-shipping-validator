"""
Cliente para consultar la API de Flapp - endpoint de tarifas (delivery-rates)
"""

import hmac
import hashlib
import base64
import json
import os
from typing import List, Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()


class FlappClient:
    """Cliente para consultar disponibilidad de despacho en Flapp"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        env: str = "sandbox",
    ):
        self.api_key = api_key or os.getenv("FLAPP_API_KEY")
        self.api_secret = api_secret or os.getenv("FLAPP_API_SECRET")
        self.env = env or os.getenv("FLAPP_ENV", "sandbox")

        if self.env == "sandbox":
            self.base_url = "https://dev-api.weflapp.com"
        else:
            self.base_url = "https://api.weflapp.com"

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "FLAPP_API_KEY y FLAPP_API_SECRET son requeridos. "
                "Configúralos en .env o pásalos al constructor."
            )

    def _generate_hmac(self, body: str) -> str:
        """Genera firma HMAC-SHA256 para el body"""
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def check_sku_availability(
        self,
        sku: str,
        phone: str,
        address1: str,
        commune: str,
        latitude: float,
        longitude: float,
        quantity: int = 1,
        price: float = 10000.0,
        stock_source_ids: Optional[List[str]] = None,
    ) -> Dict:
        """
        Consulta disponibilidad de un SKU en una dirección

        Args:
            sku: SKU del producto
            phone: Teléfono del cliente (ej: 56912345678)
            address1: Dirección principal (ej: Av. Kennedy 4700)
            commune: Comuna (ej: vitacura)
            latitude: Latitud
            longitude: Longitud
            quantity: Cantidad (default 1)
            price: Precio unitario (default 10000)
            stock_source_ids: Lista de IDs de bodegas/locales a consultar (opcional)

        Returns:
            Dict con:
            - available: bool
            - rates: List[Dict] con tarifas disponibles
            - error: str (si aplica)
            - raw_response: respuesta completa de Flapp
        """

        payload = {
            "items": [{"sku": sku, "quantity": quantity, "price": price}],
            "phone": phone,
            "shippingAddress": {
                "address1": address1,
                "commune": commune,
                "latitude": latitude,
                "longitude": longitude,
            },
        }

        if stock_source_ids:
            payload["options"] = {
                "stockSourceIds": [
                    {"stockSourceId": source_id} for source_id in stock_source_ids
                ]
            }

        # Serializar body como JSON minificado (sin espacios)
        body = json.dumps(payload, separators=(",", ":"))

        # Generar firma
        hmac_signature = self._generate_hmac(body)

        # Hacer request
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
            "X-Nomad-Hmac-Sha256": hmac_signature,
        }

        try:
            response = requests.post(
                f"{self.base_url}/integrations/generic/delivery-rates",
                data=body,  # data= para garantizar los mismos bytes
                headers=headers,
                timeout=10,
            )

            result = {
                "available": False,
                "rates": [],
                "error": None,
                "raw_response": None,
                "status_code": response.status_code,
            }

            if response.status_code == 200:
                response_data = response.json()
                rates = response_data.get("rates", [])

                result["raw_response"] = response_data
                result["rates"] = rates
                result["available"] = len(rates) > 0

                return result
            else:
                result["error"] = f"Flapp API error: {response.status_code}"
                result["raw_response"] = response.text
                return result

        except requests.exceptions.RequestException as e:
            return {
                "available": False,
                "rates": [],
                "error": str(e),
                "raw_response": None,
                "status_code": None,
            }

    def batch_check_skus(
        self,
        skus: List[str],
        phone: str,
        address1: str,
        commune: str,
        latitude: float,
        longitude: float,
    ) -> Dict[str, Dict]:
        """
        Consulta disponibilidad de múltiples SKUs

        Returns:
            Dict con sku como key y resultado como value
        """
        results = {}
        for sku in skus:
            results[sku] = self.check_sku_availability(
                sku=sku,
                phone=phone,
                address1=address1,
                commune=commune,
                latitude=latitude,
                longitude=longitude,
            )
        return results
