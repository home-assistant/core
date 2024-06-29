"""deconz conftest."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from pydeconz.websocket import Signal
import pytest

from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401
from tests.test_util.aiohttp import AiohttpClientMocker

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


# deCONZ request mocks


@pytest.fixture(name="mock_requests")
def fixture_request(
    aioclient_mock: AiohttpClientMocker,
    config_payload: dict[str, Any],
    group_payload: dict[str, Any],
    light_payload: dict[str, Any],
    sensor_payload: dict[str, Any],
) -> Callable[[str], None]:
    """Mock default UniFi requests responses."""

    def __mock_requests(host: str = HOST) -> None:
        url = f"https://{host}:{PORT}/api/{API_KEY}"

        aioclient_mock.get(
            url,
            json={
                "config": config_payload,
                "groups": group_payload,
                "lights": light_payload,
                "sensors": sensor_payload,
            },
            headers={"content-type": CONTENT_TYPE_JSON},
        )

    return __mock_requests


# Request payload fixtures


@pytest.fixture(name="alarm_system_payload")
def fixture_alarm_system_data() -> dict[str, Any]:
    """Alarm system data."""
    return {}


@pytest.fixture(name="config_payload")
def fixture_config_data() -> dict[str, Any]:
    """Config data."""
    return {}


@pytest.fixture(name="group_payload")
def fixture_group_data() -> dict[str, Any]:
    """Group data."""
    return {}


@pytest.fixture(name="light_payload")
def fixture_light_data() -> dict[str, Any]:
    """Light data."""
    return {}


@pytest.fixture(name="sensor_payload")
def fixture_sensor_data() -> dict[str, Any]:
    """Sensor data."""
    return {}


@pytest.fixture(name="config_entry_factory")
async def fixture_config_entry_factory(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> Callable[[], ConfigEntry]:
    """Fixture factory that can set up UniFi network integration."""

    async def __mock_setup_config_entry() -> ConfigEntry:
        mock_requests(config_entry.data[CONF_HOST])
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry

    return __mock_setup_config_entry


@pytest.fixture(name="config_entry_setup")
async def fixture_config_entry_setup(
    hass: HomeAssistant, config_entry_factory: Callable[[], ConfigEntry]
) -> ConfigEntry:
    """Fixture providing a set up instance of deCONZ integration."""
    return await config_entry_factory()


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
