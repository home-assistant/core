"""Meteo-France generic test utils."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_requests():
    """Stub out services that makes requests."""
    with patch("homeassistant.components.meteo_france.meteofranceClient"):
        with patch("homeassistant.components.meteo_france.VigilanceMeteoFranceProxy"):
            yield
