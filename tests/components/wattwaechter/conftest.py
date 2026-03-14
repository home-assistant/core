"""Common fixtures for WattWächter Plus tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from aio_wattwaechter.models import (
    AliveResponse,
    InfoEntry,
    MeterData,
    ObisValue,
    OtaCheckResponse,
    OtaData,
    SystemInfo,
)

from custom_components.wattwaechter.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
)

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

MOCK_METER_DATA_WITH_UNKNOWN = MeterData(
    timestamp=1704067200,
    datetime_str="2024-01-01T00:00:00",
    values={
        "1.8.0": ObisValue(value=12345.678, unit="kWh", name="Total Import"),
        "99.99.0": ObisValue(value=42.5, unit="W", name="Unknown"),
        "0.0.0": ObisValue(value="1EMH0012345678", unit="", name="Meter Number"),
    },
)

MOCK_OTA_CHECK_NO_UPDATE = OtaCheckResponse(
    ok=True,
    data=OtaData(
        update_available=False,
        version=MOCK_FW_VERSION,
        tag="",
        release_date="",
        release_note_de="",
        release_note_en="",
        last_checked=0,
        url="",
        md5="",
    ),
)

MOCK_OTA_CHECK_UPDATE = OtaCheckResponse(
    ok=True,
    data=OtaData(
        update_available=True,
        version="2.0.0",
        tag="v2.0.0",
        release_date="2024-06-01",
        release_note_en="Bug fixes and improvements",
        release_note_de="Fehlerbehebungen und Verbesserungen",
        last_checked=1704067200,
        url="",
        md5="",
    ),
)


@pytest.fixture(autouse=True, scope="session")
def _warmup_pycares_thread():
    """Pre-start pycares background thread to avoid thread-leak false positive.

    pycares starts a global daemon thread (_run_safe_shutdown_loop) the first
    time a Channel is created.  If the thread starts *during* a test, the
    pytest-homeassistant-custom-component teardown detects it as a leak.
    Starting it once at session scope puts it into every test's
    ``threads_before`` snapshot.
    """
    from pycares import _shutdown_manager

    _shutdown_manager.start()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom components in all tests."""
    yield


@pytest.fixture(autouse=True)
def mock_zeroconf(hass: HomeAssistant):
    """Mock zeroconf dependency to avoid socket access in tests."""
    hass.config.components.add("zeroconf")
    yield


@pytest.fixture
def mock_client():
    """Create a mock Wattwaechter client."""
    with patch(
        "custom_components.wattwaechter.Wattwaechter",
        autospec=True,
    ) as mock_cls:
        client = mock_cls.return_value
        client.host = MOCK_HOST
        client.alive = AsyncMock(return_value=MOCK_ALIVE_RESPONSE)
        client.system_info = AsyncMock(return_value=MOCK_SYSTEM_INFO)
        client.settings = AsyncMock(return_value=MOCK_SETTINGS)
        client.meter_data = AsyncMock(return_value=MOCK_METER_DATA)
        client.ota_check = AsyncMock(return_value=MOCK_OTA_CHECK_NO_UPDATE)
        client.ota_start = AsyncMock(return_value={"ok": True})
        yield client


@pytest.fixture
def mock_config_entry(hass: HomeAssistant):
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
