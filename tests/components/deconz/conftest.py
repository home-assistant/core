"""deconz conftest."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from pydeconz.websocket import Signal
import pytest

from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401

# Config entry fixtures

API_KEY = "1234567890ABCDEF"
BRIDGEID = "01234E56789A"
HOST = "1.2.3.4"
PORT = 80


@pytest.fixture(name="config_entry")
def fixture_config_entry(
    hass: HomeAssistant,
    config_entry_data: MappingProxyType[str, Any],
    config_entry_options: MappingProxyType[str, Any],
) -> ConfigEntry:
    """Define a config entry fixture."""
    config_entry = MockConfigEntry(
        domain=DECONZ_DOMAIN,
        entry_id="1",
        unique_id=BRIDGEID,
        data=config_entry_data,
        options=config_entry_options,
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="config_entry_data")
def fixture_config_entry_data() -> MappingProxyType[str, Any]:
    """Define a config entry data fixture."""
    return {
        CONF_API_KEY: API_KEY,
        CONF_HOST: HOST,
        CONF_PORT: PORT,
    }


@pytest.fixture(name="config_entry_options")
def fixture_config_entry_options() -> MappingProxyType[str, Any]:
    """Define a config entry options fixture."""
    return {}


# Websocket fixtures


@pytest.fixture(autouse=True)
def mock_deconz_websocket():
    """No real websocket allowed."""
    with patch("pydeconz.gateway.WSClient") as mock:

        async def make_websocket_call(data: dict | None = None, state: str = ""):
            """Generate a websocket call."""
            pydeconz_gateway_session_handler = mock.call_args[0][3]

            if data:
                mock.return_value.data = data
                await pydeconz_gateway_session_handler(signal=Signal.DATA)
            elif state:
                mock.return_value.state = state
                await pydeconz_gateway_session_handler(signal=Signal.CONNECTION_STATE)
            else:
                raise NotImplementedError

        yield make_websocket_call
