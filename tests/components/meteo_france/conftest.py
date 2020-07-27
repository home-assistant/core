"""Meteo-France generic test utils."""
import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def patch_requests():
    """Stub out services that makes requests."""
    patch_client = patch("homeassistant.components.meteo_france.meteofranceClient")
    patch_weather_alert = patch(
        "homeassistant.components.meteo_france.VigilanceMeteoFranceProxy"
    )

    with patch_client, patch_weather_alert:
        yield
