"""Common fixtures for WattWächter Plus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aio_wattwaechter.models import AliveResponse, _parse_meter_data, _parse_system_info
import pytest

from homeassistant.components.wattwaechter.const import CONF_FW_VERSION, DOMAIN
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_HOST = "192.168.1.100"
MOCK_TOKEN = "test-token-123"
MOCK_DEVICE_ID = "ABC123"
MOCK_DEVICE_NAME = "Haushalt Test"
MOCK_MAC = "AA:BB:CC:DD:EE:FF"
MOCK_MODEL = "WW-Plus"
MOCK_FW_VERSION = "1.2.3"

MOCK_CONFIG_DATA = {
    CONF_HOST: MOCK_HOST,
    CONF_TOKEN: MOCK_TOKEN,
    CONF_DEVICE_ID: MOCK_DEVICE_ID,
    CONF_MODEL: MOCK_MODEL,
    CONF_FW_VERSION: MOCK_FW_VERSION,
    CONF_MAC: MOCK_MAC,
}

MOCK_SETTINGS = MagicMock(device_name=MOCK_DEVICE_NAME)

MOCK_ALIVE_RESPONSE = AliveResponse(alive=True, version=MOCK_FW_VERSION)

MOCK_SYSTEM_INFO = _parse_system_info(
    load_json_object_fixture("system_info.json", DOMAIN)
)

MOCK_METER_DATA = _parse_meter_data(load_json_object_fixture("meter_data.json", DOMAIN))

MOCK_METER_DATA_MINIMAL = _parse_meter_data(
    load_json_object_fixture("meter_data_minimal.json", DOMAIN)
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wattwaechter.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Create a mock Wattwaechter client."""
    with (
        patch(
            "homeassistant.components.wattwaechter.Wattwaechter",
            autospec=True,
        ) as mock_cls,
        patch(
            "homeassistant.components.wattwaechter.config_flow.Wattwaechter",
            new=mock_cls,
        ),
    ):
        client = mock_cls.return_value
        client.host = MOCK_HOST
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)
        client.meter_data = AsyncMock(return_value=MOCK_METER_DATA)
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_DEVICE_NAME,
        data=MOCK_CONFIG_DATA,
        unique_id=MOCK_DEVICE_ID,
    )
    entry.add_to_hass(hass)
    return entry
