"""
Tests para el cliente Flapp
Corre con: pytest test_flapp_client.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from flapp_client import FlappClient


@pytest.fixture
def flapp_client():
    """Fixture con cliente Flapp con credenciales de test"""
    return FlappClient(
        api_key="test-key",
        api_secret="test-secret",
        env="sandbox",
    )


def test_client_initialization(flapp_client):
    """Test inicialización del cliente"""
    assert flapp_client.api_key == "test-key"
    assert flapp_client.api_secret == "test-secret"
    assert flapp_client.env == "sandbox"
    assert flapp_client.base_url == "https://dev-api.weflapp.com"


def test_client_initialization_production():
    """Test inicialización en producción"""
    client = FlappClient(
        api_key="test-key",
        api_secret="test-secret",
        env="production",
    )
    assert client.base_url == "https://api.weflapp.com"


def test_client_missing_credentials():
    """Test que falla sin credenciales"""
    with pytest.raises(ValueError):
        FlappClient(api_key=None, api_secret=None)


def test_hmac_generation(flapp_client):
    """Test generación de firma HMAC"""
    body = '{"hello":"world"}'
    signature = flapp_client._generate_hmac(body)

    # Vector de prueba de Flapp
    expected = "hMwz33Fu0LBZjwdDfJQGms43MDWHeKWSvWu9FCPREfM="
    assert signature == expected, f"Expected {expected}, got {signature}"


def test_hmac_with_minified_json(flapp_client):
    """Test HMAC con JSON minificado"""
    import json

    payload = {
        "items": [{"sku": "ABC-001", "quantity": 1, "price": 10000}],
        "phone": "56912345678",
    }

    # JSON minificado (sin espacios)
    body = json.dumps(payload, separators=(",", ":"))

    # No debería fallar
    signature = flapp_client._generate_hmac(body)
    assert isinstance(signature, str)
    assert len(signature) > 0


@patch("flapp_client.requests.post")
def test_check_sku_availability_success(mock_post, flapp_client):
    """Test consulta exitosa"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "rates": [
            {
                "id": 482910,
                "title": "Envío Express ⚡",
                "price": 3990,
                "eta": "2026-05-07T16:30:00Z",
            },
            {
                "id": 482911,
                "title": "Despacho same day",
                "price": 2990,
                "eta": "2026-05-07T20:00:00Z",
            },
        ]
    }
    mock_post.return_value = mock_response

    result = flapp_client.check_sku_availability(
        sku="ABC-001",
        phone="56912345678",
        address1="Av. Kennedy 4700",
        commune="vitacura",
        latitude=-33.4015,
        longitude=-70.5866,
    )

    assert result["available"] is True
    assert len(result["rates"]) == 2
    assert result["error"] is None
    assert result["status_code"] == 200


@patch("flapp_client.requests.post")
def test_check_sku_availability_no_rates(mock_post, flapp_client):
    """Test consulta sin tarifas disponibles"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"rates": []}
    mock_post.return_value = mock_response

    result = flapp_client.check_sku_availability(
        sku="ABC-NOEXISTE",
        phone="56912345678",
        address1="Lugar remoto",
        commune="isla-de-pascua",
        latitude=-27.1,
        longitude=-109.3,
    )

    assert result["available"] is False
    assert len(result["rates"]) == 0
    assert result["error"] is None


@patch("flapp_client.requests.post")
def test_check_sku_availability_api_error(mock_post, flapp_client):
    """Test error de la API"""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_post.return_value = mock_response

    result = flapp_client.check_sku_availability(
        sku="ABC-001",
        phone="56912345678",
        address1="Av. Kennedy 4700",
        commune="vitacura",
        latitude=-33.4015,
        longitude=-70.5866,
    )

    assert result["available"] is False
    assert result["error"] is not None
    assert "401" in result["error"]


@patch("flapp_client.requests.post")
def test_check_sku_availability_network_error(mock_post, flapp_client):
    """Test error de conexión"""
    import requests

    mock_post.side_effect = requests.ConnectionError("Connection failed")

    result = flapp_client.check_sku_availability(
        sku="ABC-001",
        phone="56912345678",
        address1="Av. Kennedy 4700",
        commune="vitacura",
        latitude=-33.4015,
        longitude=-70.5866,
    )

    assert result["available"] is False
    assert result["error"] is not None
    assert "Connection" in result["error"]


@patch("flapp_client.requests.post")
def test_batch_check_skus(mock_post, flapp_client):
    """Test consulta batch"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "rates": [
            {"id": 1, "title": "Envío Express", "price": 3990}
        ]
    }
    mock_post.return_value = mock_response

    results = flapp_client.batch_check_skus(
        skus=["ABC-001", "ABC-002"],
        phone="56912345678",
        address1="Av. Kennedy 4700",
        commune="vitacura",
        latitude=-33.4015,
        longitude=-70.5866,
    )

    assert len(results) == 2
    assert "ABC-001" in results
    assert "ABC-002" in results
    assert results["ABC-001"]["available"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
