"""The test for the fido sensor platform."""

import logging
from unittest.mock import MagicMock, patch

from pyfido.client import PyFidoError
import pytest

from homeassistant.components.fido import sensor as fido
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

CONTRACT = "123456789"


class FidoClientMock:
    """Fake Fido client."""

    def __init__(self, username, password, timeout=None, httpsession=None) -> None:
        """Fake Fido client init."""

    def get_phone_numbers(self):
        """Return Phone numbers."""
        return ["1112223344"]

    def get_data(self):
        """Return fake fido data."""
        return {"balance": 160.12, "1112223344": {"data_remaining": 100.33}}

    async def fetch_data(self):
        """Return fake fetching data."""


class FidoClientMockError(FidoClientMock):
    """Fake Fido client error."""

    async def fetch_data(self):
        """Return fake fetching data."""
        raise PyFidoError("Fake Error")


async def test_fido_sensor(hass: HomeAssistant) -> None:
    """Test the Fido number sensor."""
    with patch("homeassistant.components.fido.sensor.FidoClient", new=FidoClientMock):
        config = {
            "sensor": {
                "platform": "fido",
                "name": "fido",
                "username": "myusername",
                "password": "password",
                "monitored_variables": ["balance", "data_remaining"],
            }
        }
        with assert_setup_component(1):
            await async_setup_component(hass, "sensor", config)
            await hass.async_block_till_done()
        state = hass.states.get("sensor.fido_1112223344_balance")
        assert state.state == "160.12"
        assert state.attributes.get("number") == "1112223344"
        state = hass.states.get("sensor.fido_1112223344_data_remaining")
        assert state.state == "100.33"


async def test_error(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Test the Fido sensor errors."""
    caplog.set_level(logging.ERROR)

    config = {
        "platform": "fido",
        "name": "fido",
        "username": "myusername",
        "password": "password",
        "monitored_variables": ["balance", "data_remaining"],
    }
    fake_async_add_entities = MagicMock()
    with patch("homeassistant.components.fido.sensor.FidoClient", FidoClientMockError):
        await fido.async_setup_platform(hass, config, fake_async_add_entities)
    assert fake_async_add_entities.called is False
