"""
Tests para la API FastAPI
Corre con: pytest test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app


@pytest.fixture
def client():
    """Cliente de test para FastAPI"""
    return TestClient(app)


def test_health_check(client):
    """Test endpoint health check"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("main.flapp_client.check_sku_availability")
def test_check_availability_get_success(mock_check, client):
    """Test GET /api/check-availability exitoso"""
    mock_check.return_value = {
        "available": True,
        "rates": [
            {"id": 1, "title": "Express", "price": 3990, "eta": "2026-05-07T16:30:00Z"}
        ],
        "error": None,
    }

    response = client.get(
        "/api/check-availability",
        params={
            "sku": "ABC-001",
            "address1": "Av. Kennedy 4700",
            "commune": "vitacura",
            "latitude": -33.4015,
            "longitude": -70.5866,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sku"] == "ABC-001"
    assert data["available"] is True
    assert len(data["rates"]) == 1


@patch("main.flapp_client.check_sku_availability")
def test_check_availability_get_not_available(mock_check, client):
    """Test GET sin disponibilidad"""
    mock_check.return_value = {
        "available": False,
        "rates": [],
        "error": None,
    }

    response = client.get(
        "/api/check-availability",
        params={
            "sku": "ABC-NOEXISTE",
            "address1": "Lugar remoto",
            "commune": "isla-de-pascua",
            "latitude": -27.1,
            "longitude": -109.3,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is False
    assert data["rates"] == []


@patch("main.flapp_client.check_sku_availability")
def test_check_availability_post(mock_check, client):
    """Test POST /api/check-availability"""
    mock_check.return_value = {
        "available": True,
        "rates": [
            {"id": 1, "title": "Express", "price": 3990, "eta": "2026-05-07T16:30:00Z"}
        ],
        "error": None,
    }

    response = client.post(
        "/api/check-availability",
        json={
            "sku": "ABC-001",
            "phone": "56912345678",
            "address1": "Av. Kennedy 4700",
            "commune": "vitacura",
            "latitude": -33.4015,
            "longitude": -70.5866,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True


@patch("main.flapp_client.batch_check_skus")
def test_batch_check(mock_batch, client):
    """Test POST /api/batch-check"""
    mock_batch.return_value = {
        "ABC-001": {
            "available": True,
            "rates": [{"id": 1, "price": 3990}],
            "error": None,
        },
        "ABC-002": {
            "available": False,
            "rates": [],
            "error": None,
        },
    }

    response = client.post(
        "/api/batch-check",
        json={
            "skus": ["ABC-001", "ABC-002"],
            "phone": "56912345678",
            "address1": "Av. Kennedy 4700",
            "commune": "vitacura",
            "latitude": -33.4015,
            "longitude": -70.5866,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "ABC-001" in data
    assert "ABC-002" in data
    assert data["ABC-001"]["available"] is True
    assert data["ABC-002"]["available"] is False


def test_check_availability_missing_params(client):
    """Test GET sin parámetros requeridos"""
    response = client.get("/api/check-availability")
    assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
