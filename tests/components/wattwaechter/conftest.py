"""Common fixtures for WattWächter Plus tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aio_wattwaechter import Wattwaechter
from aio_wattwaechter.models import (
    AliveResponse,
    InfoEntry,
    MeterData,
    ObisValue,
    SystemInfo,
)
import pytest

from homeassistant.components.wattwaechter.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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
    CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
    CONF_MODEL: MOCK_MODEL,
    CONF_FW_VERSION: MOCK_FW_VERSION,
    CONF_MAC: MOCK_MAC,
}

MOCK_SETTINGS = MagicMock(device_name=MOCK_DEVICE_NAME)

MOCK_ALIVE_RESPONSE = AliveResponse(alive=True, version=MOCK_FW_VERSION)

MOCK_SYSTEM_INFO = SystemInfo(
    uptime=[InfoEntry(name="uptime", value="2d 5h 30m", unit="")],
    wifi=[
        InfoEntry(name="ssid", value="MyNetwork", unit=""),
        InfoEntry(name="signal_strength", value="-45", unit="dBm"),
        InfoEntry(name="ip_address", value=MOCK_HOST, unit=""),
        InfoEntry(name="mac_address", value=MOCK_MAC, unit=""),
        InfoEntry(name="mdns_name", value="wattwaechter-aabbccddeeff.local", unit=""),
    ],
    ap=[],
    esp=[
        InfoEntry(name="esp_id", value=MOCK_DEVICE_ID, unit=""),
        InfoEntry(name="os_version", value=MOCK_FW_VERSION, unit=""),
    ],
    heap=[InfoEntry(name="free_heap", value="120000", unit="bytes")],
)

MOCK_METER_DATA = MeterData(
    timestamp=1704067200,
    datetime_str="2024-01-01T00:00:00",
    values={
        "1.8.0": ObisValue(value=12345.678, unit="kWh", name="Total Import"),
        "2.8.0": ObisValue(value=1234.567, unit="kWh", name="Total Export"),
        "16.7.0": ObisValue(value=1500.5, unit="W", name="Active Power"),
        "32.7.0": ObisValue(value=230.1, unit="V", name="Voltage L1"),
        "31.7.0": ObisValue(value=6.52, unit="A", name="Current L1"),
        "14.7.0": ObisValue(value=50.01, unit="Hz", name="Frequency"),
        "13.7.0": ObisValue(value=0.985, unit="", name="Power Factor"),
    },
)

MOCK_METER_DATA_MINIMAL = MeterData(
    timestamp=1704067200,
    datetime_str="2024-01-01T00:00:00",
    values={
        "1.8.0": ObisValue(value=100.0, unit="kWh", name="Total Import"),
        "16.7.0": ObisValue(value=500, unit="W", name="Active Power"),
    },
)


@pytest.fixture(autouse=True)
def mock_zeroconf(hass: HomeAssistant) -> None:
    """Mock zeroconf dependency to avoid socket access in tests."""
    hass.config.components.add("zeroconf")


@pytest.fixture
def mock_client() -> Generator[Wattwaechter]:
    """Create a mock Wattwaechter client."""
    with patch(
        "homeassistant.components.wattwaechter.Wattwaechter",
        autospec=True,
    ) as mock_cls:
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
        source="user",
        unique_id=MOCK_DEVICE_ID,
        version=1,
    )
    entry.add_to_hass(hass)
    return entry
