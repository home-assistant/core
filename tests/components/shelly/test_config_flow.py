"""Test the Shelly config flow."""

from collections.abc import Generator
from dataclasses import replace
from datetime import timedelta
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

from aioshelly.const import DEFAULT_HTTP_PORT, MODEL_1, MODEL_PLUS_2PM
from aioshelly.exceptions import (
    CustomPortNotSupported,
    DeviceConnectionError,
    InvalidAuthError,
    InvalidHostError,
    RpcCallError,
)
import pytest
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.shelly import MacAddressMismatchError, config_flow
from homeassistant.components.shelly.const import (
    CONF_BLE_SCANNER_MODE,
    CONF_GEN,
    CONF_SLEEP_PERIOD,
    CONF_SSID,
    DOMAIN,
    BLEScannerMode,
)
from homeassistant.components.shelly.coordinator import ENTRY_RELOAD_COOLDOWN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info_bleak,
)
from tests.typing import WebSocketGenerator

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="mock_hostname",
    name="shelly1pm-12345",
    port=None,
    properties={ATTR_PROPERTIES_ID: "shelly1pm-12345"},
    type="mock_type",
)
DISCOVERY_INFO_WITH_MAC = ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="mock_hostname",
    name="shelly1pm-AABBCCDDEEFF",
    port=None,
    properties={ATTR_PROPERTIES_ID: "shelly1pm-AABBCCDDEEFF"},
    type="mock_type",
)
DISCOVERY_INFO_WRONG_NAME = ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    hostname="mock_hostname",
    name="Shelly Plus 2PM [DDEEFF]",
    port=None,
    properties={ATTR_PROPERTIES_ID: "shelly2pm-AABBCCDDEEFF"},
    type="mock_type",
)

# BLE manufacturer data with RPC-over-BLE enabled (flag bit 2 set)
BLE_MANUFACTURER_DATA_RPC = {
    0x0BA9: bytes([0x01, 0x04, 0x00])
}  # Flags block with RPC bit
BLE_MANUFACTURER_DATA_NO_RPC = {
    0x0BA9: bytes([0x01, 0x02, 0x00])
}  # Flags without RPC bit
BLE_MANUFACTURER_DATA_WITH_MAC = {
    0x0BA9: bytes.fromhex("0105000b30100a70d6c297bacc")
}  # Flags (0x01, 0x05, 0x00), Model (0x0b, 0x30, 0x10), MAC (0x0a, 0x70, 0xd6, 0xc2, 0x97, 0xba, 0xcc)
# Device WiFi MAC: 70d6c297bacc (little-endian) -> CCBA97C2D670 (reversed to big-endian)
# BLE MAC is typically device MAC + 2: CCBA97C2D670 + 2 = CC:BA:97:C2:D6:72

BLE_MANUFACTURER_DATA_WITH_MAC_UNKNOWN_MODEL = {
    0x0BA9: bytes.fromhex("0105000b99990a70d6c297bacc")
}  # Flags (0x01, 0x05, 0x00), Model (0x0b, 0x99, 0x99) - unknown model ID, MAC (0x0a, 0x70, 0xd6, 0xc2, 0x97, 0xba, 0xcc)

BLE_MANUFACTURER_DATA_FOR_CLEAR_TEST = {
    0x0BA9: bytes.fromhex("0105000b30100a00eeddccbbaa")
}  # Flags (0x01, 0x05, 0x00), Model (0x0b, 0x30, 0x10), MAC (0x0a, 0x00, 0xee, 0xdd, 0xcc, 0xbb, 0xaa)
# Device WiFi MAC: 00eeddccbbaa (little-endian) -> AABBCCDDEE00 (reversed to big-endian)

BLE_DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name="ShellyPlus2PM-C049EF8873E8",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data=BLE_MANUFACTURER_DATA_RPC,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:FF",
        name="ShellyPlus2PM-C049EF8873E8",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_RPC,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_FOR_CLEAR_TEST = BluetoothServiceInfoBleak(
    name="ShellyPlus2PM-AABBCCDDEE00",
    address="AA:BB:CC:DD:EE:00",
    rssi=-60,
    manufacturer_data=BLE_MANUFACTURER_DATA_FOR_CLEAR_TEST,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:00",
        name="ShellyPlus2PM-AABBCCDDEE00",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_FOR_CLEAR_TEST,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_NO_RPC = BluetoothServiceInfoBleak(
    name="ShellyPlus2PM-C049EF8873E8",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data=BLE_MANUFACTURER_DATA_NO_RPC,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:FF",
        name="ShellyPlus2PM-C049EF8873E8",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_NO_RPC,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_INVALID_NAME = BluetoothServiceInfoBleak(
    name="InvalidName",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data=BLE_MANUFACTURER_DATA_RPC,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:FF",
        name="InvalidName",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_RPC,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_MAC_IN_MANUFACTURER_DATA = BluetoothServiceInfoBleak(
    name="CC:BA:97:C2:D6:72",  # BLE address as name (newer devices)
    address="CC:BA:97:C2:D6:72",  # BLE address may differ from device MAC
    rssi=-32,
    manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="CC:BA:97:C2:D6:72",
        name="CC:BA:97:C2:D6:72",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_MAC_UNKNOWN_MODEL = BluetoothServiceInfoBleak(
    name="CC:BA:97:C2:D6:72",  # BLE address as name (newer devices)
    address="CC:BA:97:C2:D6:72",  # BLE address may differ from device MAC
    rssi=-32,
    manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC_UNKNOWN_MODEL,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="CC:BA:97:C2:D6:72",
        name="CC:BA:97:C2:D6:72",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC_UNKNOWN_MODEL,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_NO_DEVICE = BluetoothServiceInfoBleak(
    name="ShellyPlus2PM-C049EF8873E8",
    address="00:00:00:00:00:00",  # Invalid address that won't be found
    rssi=-60,
    manufacturer_data=BLE_MANUFACTURER_DATA_RPC,
    service_uuids=[],
    service_data={},
    source="local",
    device=generate_ble_device(
        address="00:00:00:00:00:00",
        name="ShellyPlus2PM-C049EF8873E8",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_RPC,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

BLE_DISCOVERY_INFO_GEN3 = BluetoothServiceInfoBleak(
    name="ShellyPlusGen3",
    address="AA:BB:CC:DD:EE:FF",
    rssi=-60,
    manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC,
    service_data={},
    service_uuids=[],
    source="local",
    device=generate_ble_device(
        address="AA:BB:CC:DD:EE:FF",
        name="ShellyPlusGen3",
    ),
    advertisement=generate_advertisement_data(
        manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC,
    ),
    time=0,
    connectable=True,
    tx_power=-127,
)

# Mock HTTP zeroconf service info for shellyplus2pm-AABBCCDDEEFF
MOCK_HTTP_ZEROCONF_SERVICE_INFO = AsyncServiceInfo(
    type_="_http._tcp.local.",
    name="shellyplus2pm-AABBCCDDEEFF._http._tcp.local.",
    port=80,
    addresses=[ip_address("192.168.1.100").packed],
    server="shellyplus2pm-AABBCCDDEEFF.local.",
)

# Mock Shelly zeroconf service info for shellyplus2pm-CCBA97C2D670
MOCK_SHELLY_ZEROCONF_SERVICE_INFO = AsyncServiceInfo(
    type_="_http._tcp.local.",
    name="shellyplus2pm-CCBA97C2D670._http._tcp.local.",
    port=80,
    addresses=[ip_address("192.168.1.100").packed],
    server="shellyplus2pm-CCBA97C2D670.local.",
)

# Mock device info returned by get_info for BLE provisioned devices
MOCK_DEVICE_INFO = {
    "mac": "C049EF8873E8",
    "model": MODEL_PLUS_2PM,
    "auth": False,
    "gen": 2,
}


@pytest.fixture(autouse=True)
def mock_provisioning_timeout() -> Generator[None]:
    """Patch provisioning timeout to 0 for tests."""
    with patch("homeassistant.components.shelly.config_flow.PROVISIONING_TIMEOUT", 0):
        yield


@pytest.fixture(autouse=True)
def mock_zeroconf_async_get_instance() -> Generator[AsyncMock]:
    """Patch zeroconf async_get_async_instance for tests."""
    with patch(
        "homeassistant.components.shelly.config_flow.zeroconf.async_get_async_instance"
    ) as mock_aiozc:
        mock_aiozc.return_value = AsyncMock()
        yield mock_aiozc


@pytest.fixture
def mock_wifi_scan() -> Generator[AsyncMock]:
    """Mock async_scan_wifi_networks."""
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        new=AsyncMock(return_value=[{"ssid": "TestNetwork", "rssi": -50, "auth": 2}]),
    ) as mock_scan:
        yield mock_scan


@pytest.fixture
def mock_wifi_provision() -> Generator[AsyncMock]:
    """Mock async_provision_wifi."""
    with patch(
        "homeassistant.components.shelly.config_flow.async_provision_wifi",
        new=AsyncMock(),
    ) as mock_provision:
        yield mock_provision


@pytest.fixture(autouse=True)
def mock_discovery() -> Generator[AsyncMock]:
    """Mock device discovery to return empty by default."""
    with patch(
        "homeassistant.components.shelly.config_flow.async_discover_devices",
        return_value=[],
    ) as mock_disc:
        yield mock_disc


def create_mock_rpc_device(
    name: str = "Test Device", model: str | None = MODEL_PLUS_2PM
) -> AsyncMock:
    """Create a mock RPC device for provisioning tests."""
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.name = name
    mock_device.firmware_version = "1.0.0"
    mock_device.status = {"sys": {}}
    mock_device.xmod_info = {}
    mock_device.shelly = {"model": model}
    mock_device.wifi_setconfig = AsyncMock(return_value={})
    mock_device.ble_setconfig = AsyncMock(return_value={"restart_required": False})
    mock_device.shutdown = AsyncMock()
    return mock_device


@pytest.mark.parametrize(
    ("gen", "model", "port"),
    [
        (1, MODEL_1, DEFAULT_HTTP_PORT),
        (2, MODEL_PLUS_2PM, DEFAULT_HTTP_PORT),
        (3, MODEL_PLUS_2PM, 11200),
    ],
)
async def test_form(
    hass: HomeAssistant,
    gen: int,
    model: str,
    port: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "test-mac",
                "type": MODEL_1,
                "auth": False,
                "gen": gen,
                "port": port,
            },
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: port},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: port,
        CONF_MODEL: model,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: gen,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_overrides_existing_discovery(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test setting up from the user flow when the devices is already discovered."""
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "AABBCCDDEEFF",
            "model": MODEL_PLUS_2PM,
            "auth": False,
            "gen": 2,
            "port": 80,
        },
    ):
        discovery_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZeroconfServiceInfo(
                ip_address=ip_address("1.1.1.1"),
                ip_addresses=[ip_address("1.1.1.1")],
                hostname="mock_hostname",
                name="shelly2pm-aabbccddeeff",
                port=None,
                properties={ATTR_PROPERTIES_ID: "shelly2pm-aabbccddeeff"},
                type="mock_type",
            ),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert discovery_result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert result["context"]["unique_id"] == "AABBCCDDEEFF"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    # discovery flow should have been aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_form_gen1_custom_port(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={"mac": "test-mac", "type": MODEL_1, "gen": 1},
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create",
            side_effect=CustomPortNotSupported,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: "1100"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "custom_port_not_supported"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "gen": 1},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_HTTP_PORT},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("gen", "model", "user_input", "username"),
    [
        (
            1,
            MODEL_1,
            {CONF_USERNAME: "test user", CONF_PASSWORD: "test1 password"},
            "test user",
        ),
        (
            2,
            MODEL_PLUS_2PM,
            {CONF_PASSWORD: "test2 password"},
            "admin",
        ),
        (
            3,
            MODEL_PLUS_2PM,
            {CONF_PASSWORD: "test2 password"},
            "admin",
        ),
    ],
)
async def test_form_auth(
    hass: HomeAssistant,
    gen: int,
    model: str,
    user_input: dict[str, str],
    username: str,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test manual configuration if auth is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": True, "gen": gen},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: model,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: gen,
        CONF_USERNAME: username,
        CONF_PASSWORD: user_input[CONF_PASSWORD],
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (InvalidHostError, "invalid_host"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors_get_info(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup: AsyncMock,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.shelly.config_flow.get_info", side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "gen": 1},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_missing_model_key(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test we handle missing Shelly model key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    monkeypatch.setattr(mock_rpc_device, "shelly", {"gen": 2})
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False, "gen": "2"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


async def test_form_missing_model_key_auth_enabled(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test we handle missing Shelly model key when auth enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    monkeypatch.setattr(mock_rpc_device, "shelly", {"gen": 2})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "1234"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


async def test_form_missing_model_key_zeroconf(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test we handle missing Shelly model key via zeroconf."""
    monkeypatch.setattr(mock_rpc_device, "shelly", {"gen": 2})
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (MacAddressMismatchError, "mac_address_mismatch"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors_test_connection(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={"mac": "test-mac", "auth": False},
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create", new=AsyncMock(side_effect=exc)
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"


async def test_user_setup_ignored_device(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test user can successfully setup an ignored device."""

    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0"},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_no_devices_discovered(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test user flow with no discovered devices redirects to manual entry."""
    # mock_discovery fixture already returns empty list by default
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should redirect to manual entry step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_manual"

    # Complete manual entry
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac",
            "type": MODEL_1,
            "auth": False,
            "gen": 1,
            "port": DEFAULT_HTTP_PORT,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1", CONF_PORT: DEFAULT_HTTP_PORT},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"


async def test_user_flow_with_zeroconf_devices(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test user flow shows discovered Zeroconf devices."""
    # Mock zeroconf discovery to return a device
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should show form with discovered device
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check device is in the options
    schema = result["data_schema"].schema
    device_selector = schema[CONF_DEVICE]
    options = device_selector.config["options"]

    # Should have the discovered device plus manual entry
    # Options is now a list of dicts with 'value' and 'label' keys
    option_values = {opt["value"]: opt["label"] for opt in options}
    assert "AABBCCDDEEFF" in option_values  # MAC as value
    assert "manual" in option_values
    assert option_values["AABBCCDDEEFF"] == "shellyplus2pm-AABBCCDDEEFF"
    assert (
        option_values["manual"] == "manual"
    )  # Translation key, not the translated text

    # Select the discovered device and complete setup
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test Zeroconf Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "AABBCCDDEEFF"
    assert result["data"][CONF_HOST] == "192.168.1.100"


async def test_user_flow_select_zeroconf_device(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test selecting a discovered Zeroconf device completes setup."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select the discovered device
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "AABBCCDDEEFF",
            "model": MODEL_PLUS_2PM,
            "auth": False,
            "gen": 2,
            "port": 80,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},  # Select by MAC
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PORT] == 80


async def test_user_flow_select_manual_entry(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test selecting manual entry from device list."""
    # Mock zeroconf discovery with a device
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select manual entry
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: "manual"},
    )

    # Should go to manual entry step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_manual"

    # Complete manual entry
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac-2",
            "type": MODEL_1,
            "auth": False,
            "gen": 1,
            "port": DEFAULT_HTTP_PORT,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200", CONF_PORT: DEFAULT_HTTP_PORT},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.168.1.200"


async def test_user_flow_both_ble_and_zeroconf_prefers_zeroconf(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test device discovered via both BLE and Zeroconf prefers Zeroconf."""
    # Mock zeroconf discovery - same MAC as BLE device
    mock_discovery.return_value = [MOCK_SHELLY_ZEROCONF_SERVICE_INFO]

    # Inject BLE device with same MAC (from manufacturer data)
    # The manufacturer data contains WiFi MAC CCBA97C2D670
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO_GEN3)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check device list - should only have one device (Zeroconf, not BLE)
    schema = result["data_schema"].schema
    device_selector = schema[CONF_DEVICE]
    options = {opt["value"]: opt["label"] for opt in device_selector.config["options"]}

    # Should have the device with MAC as key
    assert "CCBA97C2D670" in options
    assert options["CCBA97C2D670"] == "shellyplus2pm-CCBA97C2D670"
    # Should also have manual entry
    assert "manual" in options

    # Verify only 2 options (device + manual), not 3 (no duplicate)
    assert len(options) == 2

    # Select the device and verify it uses Zeroconf connection info
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "CCBA97C2D670",
            "model": MODEL_PLUS_2PM,
            "auth": False,
            "gen": 2,
            "port": 80,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "CCBA97C2D670"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Verify it used Zeroconf host (192.168.1.100) not BLE provisioning
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PORT] == 80


async def test_user_flow_with_ble_devices(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test user flow shows discovered BLE devices."""
    # Mock empty zeroconf discovery
    mock_discovery.return_value = []

    # Inject BLE device with RPC-over-BLE enabled
    # The manufacturer data contains WiFi MAC CCBA97C2D670
    inject_bluetooth_service_info_bleak(
        hass,
        BluetoothServiceInfoBleak(
            name="ShellyPlusGen3",  # Name without MAC so it uses manufacturer data
            address="AA:BB:CC:DD:EE:FF",
            rssi=-60,
            manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC,
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(
                address="AA:BB:CC:DD:EE:FF",
                name="ShellyPlusGen3",
            ),
            advertisement=generate_advertisement_data(
                manufacturer_data=BLE_MANUFACTURER_DATA_WITH_MAC,
            ),
            time=0,
            connectable=True,
            tx_power=-127,
        ),
    )

    # Wait for bluetooth discovery to process
    await hass.async_block_till_done()

    # Abort any auto-discovered bluetooth flows
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    for flow in flows:
        if flow["context"]["source"] == config_entries.SOURCE_BLUETOOTH:
            await hass.config_entries.flow.async_abort(flow["flow_id"])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should show form with discovered BLE device
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check device is in the options
    schema = result["data_schema"].schema
    device_selector = schema[CONF_DEVICE]
    options = {opt["value"]: opt["label"] for opt in device_selector.config["options"]}

    # Should have the discovered BLE device plus manual entry
    # MAC from manufacturer data: CCBA97C2D670
    assert "CCBA97C2D670" in options
    assert "manual" in options
    # Device name should be from model ID + MAC
    assert "Shelly1MiniGen4-CCBA97C2D670" in options["CCBA97C2D670"]

    # Select the BLE device and complete provisioning flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: "CCBA97C2D670"},
    )

    # Should go to bluetooth_confirm step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Complete WiFi provisioning
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "TestNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    # Select network and enter WiFi credentials to complete
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("192.168.1.100", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "CCBA97C2D670",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "TestNetwork", CONF_PASSWORD: "test_password"},
        )

        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "CCBA97C2D670"


async def test_user_flow_filters_already_configured_devices(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test already configured devices are filtered from discovery list."""
    # Add an existing configured entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={CONF_HOST: "192.168.1.50"},
    )
    entry.add_to_hass(hass)

    # Mock zeroconf discovery with two devices
    mock_service_info_1 = AsyncServiceInfo(
        type_="_http._tcp.local.",
        name="shellyplus2pm-AABBCCDDEEFF._http._tcp.local.",
        port=80,
        addresses=[ip_address("192.168.1.100").packed],
        server="shellyplus2pm-AABBCCDDEEFF.local.",
    )
    mock_service_info_2 = AsyncServiceInfo(
        type_="_http._tcp.local.",
        name="shellyplus2pm-112233445566._http._tcp.local.",
        port=80,
        addresses=[ip_address("192.168.1.101").packed],
        server="shellyplus2pm-112233445566.local.",
    )
    mock_discovery.return_value = [mock_service_info_1, mock_service_info_2]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check device list - should only have unconfigured device
    schema = result["data_schema"].schema
    device_selector = schema[CONF_DEVICE]
    options = {opt["value"]: opt["label"] for opt in device_selector.config["options"]}

    # Should NOT have the already configured device
    assert "AABBCCDDEEFF" not in options
    # Should have the new device
    assert "112233445566" in options
    # Should have manual entry
    assert "manual" in options

    # Select the unconfigured device and complete setup
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "112233445566",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "112233445566"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Device"
    assert result["data"][CONF_HOST] == "192.168.1.101"


async def test_user_flow_includes_ignored_devices(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test ignored devices are included in discovery list for reconfiguration."""
    # Add an ignored entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={CONF_HOST: "192.168.1.50"},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    # Mock zeroconf discovery with the ignored device
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check device list - should include the ignored device
    schema = result["data_schema"].schema
    device_selector = schema[CONF_DEVICE]
    options = {opt["value"]: opt["label"] for opt in device_selector.config["options"]}

    # Should have the ignored device (for potential reconfiguration)
    assert "AABBCCDDEEFF" in options
    assert options["AABBCCDDEEFF"] == "shellyplus2pm-AABBCCDDEEFF"

    # Select the ignored device and complete setup
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test Ignored Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Ignored Device"


async def test_user_flow_aborts_when_another_flow_finishes_while_in_progress(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test that user flow aborts when another flow finishes and creates a config entry."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Check device list
    schema = result["data_schema"].schema
    device_selector = schema[CONF_DEVICE]
    options = {opt["value"]: opt["label"] for opt in device_selector.config["options"]}

    assert "AABBCCDDEEFF" in options
    assert options["AABBCCDDEEFF"] == "shellyplus2pm-AABBCCDDEEFF"

    # Now simulate another flow configuring the device while user is on the selection form
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)

    # User selects the device - should abort because it's now configured
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "AABBCCDDEEFF",
            "model": MODEL_PLUS_2PM,
            "auth": False,
            "gen": 2,
            "port": 80,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_zeroconf_device_connection_error(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test connection error when getting info from Zeroconf device."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select the device but connection fails when getting info
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_zeroconf_device_validation_connection_error(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test connection error during validation of Zeroconf device."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select the device but connection fails during validation
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_PLUS_2PM,
                "auth": False,  # No auth required, will proceed to validate_input
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            side_effect=DeviceConnectionError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_flow_zeroconf_device_requires_auth(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_block_device: Mock,
) -> None:
    """Test selecting Zeroconf device that requires authentication."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select device that requires auth
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "AABBCCDDEEFF",
            "model": MODEL_1,
            "auth": True,  # Requires auth
            "gen": 1,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    # Should go to credentials step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    # Complete credentials and create entry
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_1,
                "auth": False,  # Auth passed with credentials
                "gen": 1,
                "port": 80,
            },
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create",
            return_value=mock_block_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"


async def test_user_flow_zeroconf_invalid_mac_filtered(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test Zeroconf device with invalid MAC is filtered."""
    # Mock zeroconf discovery with invalid device name (no MAC)
    mock_service_info = AsyncServiceInfo(
        type_="_http._tcp.local.",
        name="invalid-device-name._http._tcp.local.",
        port=80,
        addresses=[ip_address("192.168.1.100").packed],
        server="invalid-device-name.local.",
    )
    mock_discovery.return_value = [mock_service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should redirect to manual entry (no valid devices)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_manual"

    # Complete manual entry
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Manual Entry Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100", CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Manual Entry Device"


async def test_user_flow_zeroconf_no_ipv4_filtered(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test Zeroconf device with no IPv4 address is filtered."""
    # Mock zeroconf discovery with only IPv6 (no IPv4)
    mock_service_info = AsyncServiceInfo(
        type_="_http._tcp.local.",
        name="shellyplus2pm-AABBCCDDEEFF._http._tcp.local.",
        port=80,
        addresses=[],  # No addresses
        server="shellyplus2pm-AABBCCDDEEFF.local.",
    )
    mock_discovery.return_value = [mock_service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should redirect to manual entry (no valid devices)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_manual"

    # Complete manual entry
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "112233445566",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Manual IPv4 Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.101", CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Manual IPv4 Device"


async def test_user_flow_ble_device_without_rpc_over_ble_filtered(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test BLE device without RPC-over-BLE is filtered."""
    # Mock empty zeroconf discovery
    mock_discovery.return_value = []

    # Inject BLE device WITHOUT RPC-over-BLE (empty manufacturer data)
    inject_bluetooth_service_info_bleak(
        hass,
        BluetoothServiceInfoBleak(
            name="ShellyPlusGen3-AABBCCDDEEFF",
            address="AA:BB:CC:DD:EE:FF",
            rssi=-60,
            manufacturer_data={},  # No manufacturer data = no RPC-over-BLE
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(
                address="AA:BB:CC:DD:EE:FF",
                name="ShellyPlusGen3-AABBCCDDEEFF",
            ),
            advertisement=generate_advertisement_data(),
            time=0,
            connectable=True,
            tx_power=-127,
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should redirect to manual entry (no valid devices)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_manual"

    # Complete manual entry
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "DDEEFF112233",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Manual BLE Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.102", CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Manual BLE Device"


async def test_user_flow_select_zeroconf_device_mac_mismatch(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test MAC address mismatch when selecting Zeroconf device."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select device but MAC address doesn't match
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            side_effect=MacAddressMismatchError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mac_address_mismatch"


async def test_user_flow_select_zeroconf_device_custom_port_not_supported(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test custom port not supported when selecting Zeroconf device."""
    # Mock zeroconf discovery
    mock_service_info = AsyncServiceInfo(
        type_="_http._tcp.local.",
        name="shellyplus2pm-AABBCCDDEEFF._http._tcp.local.",
        port=8080,  # Custom port
        addresses=[ip_address("192.168.1.100").packed],
        server="shellyplus2pm-AABBCCDDEEFF.local.",
    )
    mock_discovery.return_value = [mock_service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select device but custom port not supported
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
                "port": 8080,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            side_effect=CustomPortNotSupported,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "custom_port_not_supported"


async def test_user_flow_select_zeroconf_device_not_fully_provisioned(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test firmware not fully provisioned when selecting Zeroconf device."""
    # Mock zeroconf discovery
    mock_discovery.return_value = [MOCK_HTTP_ZEROCONF_SERVICE_INFO]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select device but firmware not fully provisioned (empty model)
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "AABBCCDDEEFF",
                "model": "",  # Empty model indicates not fully provisioned
                "auth": False,
                "gen": 2,
                "port": 80,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("shellyplus2pm-AABBCCDDEEFF", model=""),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE: "AABBCCDDEEFF"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


async def test_user_flow_select_ble_device(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
) -> None:
    """Test selecting a BLE device goes to provisioning flow."""
    # Mock empty zeroconf discovery
    mock_discovery.return_value = []

    # Inject BLE device with RPC-over-BLE enabled (no discovery flow created)
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO_GEN3)

    # Wait for bluetooth discovery to process
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select the BLE device
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE: "CCBA97C2D670"},  # MAC from manufacturer data
    )

    # Should go to bluetooth_confirm step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    # Confirm BLE provisioning and scan for WiFi networks
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[
            {"ssid": "MyNetwork", "rssi": -50, "auth": 2},
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi_scan"

    # Select network and enter password to provision
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("192.168.1.200", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "CCBA97C2D670",
                "model": MODEL_PLUS_2PM,
                "auth": False,
                "gen": 2,
            },
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test BLE Device"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "wifi_password"},
        )

        # Should show progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # Wait for provision task to complete
        await hass.async_block_till_done()

        # Complete provisioning
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "CCBA97C2D670"
    assert result["title"] == "Test BLE Device"


async def test_user_flow_filters_devices_with_active_discovery_flows(
    hass: HomeAssistant,
    mock_discovery: AsyncMock,
    mock_rpc_device: Mock,
) -> None:
    """Test user flow filters out devices that already have discovery flows."""
    # Mock empty zeroconf discovery
    mock_discovery.return_value = []

    # Inject BLE device with RPC-over-BLE enabled
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO_GEN3)

    # Wait for bluetooth discovery to process
    await hass.async_block_till_done()

    # Start a bluetooth discovery flow to simulate auto-discovery
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=BLE_DISCOVERY_INFO_GEN3,
    )

    # Start a user flow - should go to manual entry since the only
    # discovered device already has an active discovery flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should go directly to manual entry since the BLE device is filtered
    # out (it already has an active discovery flow being offered to the user)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_manual"

    # Complete the manual entry flow to reach terminal state
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "aabbccddeeff", "model": MODEL_PLUS_2PM, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.10.10.10"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "10.10.10.10",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_SLEEP_PERIOD: 0,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_GEN: 2,
    }


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (InvalidAuthError, "invalid_auth"),
        (DeviceConnectionError, "cannot_connect"),
        (MacAddressMismatchError, "mac_address_mismatch"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection_gen1(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup: AsyncMock,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors in Gen1 authenticated devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    with patch(
        "aioshelly.block_device.BlockDevice.create",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test username", CONF_PASSWORD: "test password"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "test username", CONF_PASSWORD: "test password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
        CONF_USERNAME: "test username",
        CONF_PASSWORD: "test password",
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (InvalidAuthError, "invalid_auth"),
        (MacAddressMismatchError, "mac_address_mismatch"),
        (ValueError, "unknown"),
    ],
)
async def test_form_auth_errors_test_connection_gen2(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    mock_setup: AsyncMock,
    mock_setup_entry: AsyncMock,
    exc: Exception,
    base_error: str,
) -> None:
    """Test we handle errors in Gen2 authenticated devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    with patch(
        "aioshelly.rpc_device.RpcDevice.create",
        side_effect=exc,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: "test password"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "auth": True, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "test password"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: "SNSW-002P16EU",
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "test password",
    }
    assert result["context"]["unique_id"] == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("gen", "model", "get_info"),
    [
        (
            1,
            MODEL_1,
            {"mac": "test-mac", "type": MODEL_1, "auth": False, "gen": 1},
        ),
        (
            2,
            MODEL_PLUS_2PM,
            {"mac": "test-mac", "model": MODEL_PLUS_2PM, "auth": False, "gen": 2},
        ),
        (
            3,
            MODEL_PLUS_2PM,
            {"mac": "test-mac", "model": MODEL_PLUS_2PM, "auth": False, "gen": 3},
        ),
    ],
)
async def test_zeroconf(
    hass: HomeAssistant,
    gen: int,
    model: str,
    get_info: dict[str, Any],
    mock_block_device: Mock,
    mock_rpc_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info", return_value=get_info
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"
        assert context["confirm_only"] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_MODEL: model,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: gen,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test sleeping device configuration via zeroconf."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 10, "unit": "m"},
    )
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac",
            "type": MODEL_1,
            "auth": False,
            "sleep_mode": True,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "shelly1pm-12345"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 600,
        CONF_GEN: 1,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sleeping_device_error(hass: HomeAssistant) -> None:
    """Test sleeping device configuration via zeroconf with error."""
    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "test-mac",
                "type": MODEL_1,
                "auth": False,
                "sleep_mode": True,
            },
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create",
            new=AsyncMock(side_effect=DeviceConnectionError),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow_abort_setup_retry(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ble options abort if device is in setup retry."""
    monkeypatch.setattr(
        mock_rpc_device, "initialize", AsyncMock(side_effect=DeviceConnectionError)
    )
    entry = await init_integration(hass, 2)

    assert entry.state is ConfigEntryState.SETUP_RETRY

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_options_flow_abort_no_scripts_support(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ble options abort if device does not support scripts."""
    monkeypatch.setattr(
        mock_rpc_device, "supports_scripts", AsyncMock(return_value=False)
    )
    entry = await init_integration(hass, 2)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_scripts_support"


async def test_options_flow_abort_zigbee_firmware(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test ble options abort if Zigbee firmware is active."""
    monkeypatch.setattr(mock_rpc_device, "zigbee_firmware", True)
    entry = await init_integration(hass, 4)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zigbee_firmware"


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry got updated with latest IP
    assert entry.data[CONF_HOST] == "1.1.1.1"


async def test_zeroconf_ignored(hass: HomeAssistant) -> None:
    """Test zeroconf when the device was previously ignored."""

    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_with_wifi_ap_ip(hass: HomeAssistant) -> None:
    """Test we ignore the Wi-FI AP IP."""

    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "2.2.2.2"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=replace(
                DISCOVERY_INFO, ip_address=ip_address(config_flow.INTERNAL_WIFI_AP_IP)
            ),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Test config entry was not updated with the wifi ap ip
    assert entry.data[CONF_HOST] == "2.2.2.2"


async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_require_auth(
    hass: HomeAssistant,
    mock_block_device: Mock,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test zeroconf if auth is required."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": True},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test username", CONF_PASSWORD: "test password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_1,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 1,
        CONF_USERNAME: "test username",
        CONF_PASSWORD: "test password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("gen", "user_input"),
    [
        (1, {CONF_USERNAME: "test user", CONF_PASSWORD: "test1 password"}),
        (2, {CONF_PASSWORD: "test2 password"}),
        (3, {CONF_PASSWORD: "test2 password"}),
    ],
)
async def test_reauth_successful(
    hass: HomeAssistant,
    gen: int,
    user_input: dict[str, str],
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test starting a reauthentication flow."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": True, "gen": gen},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.parametrize(
    ("gen", "user_input"),
    [
        (1, {CONF_USERNAME: "test user", CONF_PASSWORD: "test1 password"}),
        (2, {CONF_PASSWORD: "test2 password"}),
        (3, {CONF_PASSWORD: "test2 password"}),
    ],
)
@pytest.mark.parametrize(
    ("exc", "abort_reason"),
    [
        (DeviceConnectionError, "reauth_unsuccessful"),
        (MacAddressMismatchError, "mac_address_mismatch"),
    ],
)
async def test_reauth_unsuccessful(
    hass: HomeAssistant,
    gen: int,
    user_input: dict[str, str],
    exc: Exception,
    abort_reason: str,
) -> None:
    """Test reauthentication flow failed."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "test-mac",
                "type": MODEL_1,
                "auth": True,
                "gen": gen,
            },
        ),
        patch(
            "aioshelly.block_device.BlockDevice.create", new=AsyncMock(side_effect=exc)
        ),
        patch("aioshelly.rpc_device.RpcDevice.create", new=AsyncMock(side_effect=exc)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == abort_reason


async def test_reauth_get_info_error(hass: HomeAssistant) -> None:
    """Test reauthentication flow failed with error in get_info()."""
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0", CONF_GEN: 2}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "test2 password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_unsuccessful"


async def test_options_flow_disabled_gen_1(
    hass: HomeAssistant, mock_block_device: Mock, hass_ws_client: WebSocketGenerator
) -> None:
    """Test options are disabled for gen1 devices."""
    await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, 1)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "shelly",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is False
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_enabled_gen_2(
    hass: HomeAssistant, mock_rpc_device: Mock, hass_ws_client: WebSocketGenerator
) -> None:
    """Test options are enabled for gen2 devices."""
    await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, 2)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "shelly",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is True
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_disabled_sleepy_gen_2(
    hass: HomeAssistant, mock_rpc_device: Mock, hass_ws_client: WebSocketGenerator
) -> None:
    """Test options are disabled for sleepy gen2 devices."""
    await async_setup_component(hass, "config", {})
    entry = await init_integration(hass, 2, sleep_period=10)

    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            "id": 5,
            "type": "config_entries/get",
            "domain": "shelly",
        }
    )
    response = await ws_client.receive_json()
    assert response["result"][0]["supports_options"] is False
    await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow_ble(hass: HomeAssistant, mock_rpc_device: Mock) -> None:
    """Test setting ble options for gen2 devices."""
    entry = await init_integration(hass, 2)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.DISABLED,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] is BLEScannerMode.DISABLED

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] is BLEScannerMode.ACTIVE

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] is None

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLE_SCANNER_MODE: BLEScannerMode.PASSIVE,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BLE_SCANNER_MODE] is BLEScannerMode.PASSIVE

    await hass.config_entries.async_unload(entry.entry_id)


async def test_zeroconf_already_configured_triggers_refresh_mac_in_name(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zeroconf discovery triggers refresh when the mac is in the device name."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 0,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO_WITH_MAC,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 2


async def test_zeroconf_already_configured_triggers_refresh(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zeroconf discovery triggers refresh when the mac is obtained via get_info."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 0,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 2


async def test_zeroconf_sleeping_device_not_triggers_refresh(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery does not triggers refresh for sleeping device."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert len(mock_rpc_device.initialize.mock_calls) == 1
    assert "device did not update" not in caplog.text


async def test_zeroconf_sleeping_device_attempts_configure(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery configures a sleeping device outbound websocket."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_rpc_device.update_outbound_websocket.mock_calls == []

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert "device did not update" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    assert mock_rpc_device.update_outbound_websocket.mock_calls == [
        call("ws://10.10.10.10:8123/api/shelly/ws")
    ]


async def test_zeroconf_sleeping_device_attempts_configure_ws_disabled(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery configures a sleeping device outbound websocket when its disabled."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    monkeypatch.setitem(
        mock_rpc_device.config, "ws", {"enable": False, "server": "ws://oldha"}
    )
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_rpc_device.update_outbound_websocket.mock_calls == []

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert "device did not update" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    assert mock_rpc_device.update_outbound_websocket.mock_calls == [
        call("ws://10.10.10.10:8123/api/shelly/ws")
    ]


async def test_zeroconf_sleeping_device_attempts_configure_no_url_available(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test zeroconf discovery for sleeping device with no hass url."""
    hass.config.internal_url = None
    hass.config.external_url = None
    hass.config.api = None
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="AABBCCDDEEFF",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_GEN: 2,
            CONF_SLEEP_PERIOD: 1000,
            CONF_MODEL: MODEL_1,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mock_rpc_device.mock_disconnected()
    await hass.async_block_till_done()

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "online, resuming setup" in caplog.text
    assert len(mock_rpc_device.initialize.mock_calls) == 1

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "AABBCCDDEEFF", "type": MODEL_1, "auth": False},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_rpc_device.update_outbound_websocket.mock_calls == []

    monkeypatch.setattr(mock_rpc_device, "connected", True)
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()
    assert "device did not update" not in caplog.text

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_disconnected()
    # No url available so no attempt to configure the device
    assert mock_rpc_device.update_outbound_websocket.mock_calls == []


async def test_sleeping_device_gen2_with_new_firmware(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test sleeping device Gen2 with firmware 1.0.0 or later."""
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 666)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={"mac": "test-mac", "gen": 2},
        ),
        patch("homeassistant.components.shelly.async_setup", return_value=True),
        patch(
            "homeassistant.components.shelly.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "1.1.1.1"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: DEFAULT_HTTP_PORT,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 666,
        CONF_GEN: 2,
    }


@pytest.mark.parametrize(CONF_GEN, [1, 2, 3])
async def test_reconfigure_successful(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test starting a reconfiguration flow."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False, "gen": gen},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "10.10.10.10", CONF_PORT: 99, CONF_GEN: gen}


@pytest.mark.parametrize("gen", [1, 2, 3])
async def test_reconfigure_unsuccessful(
    hass: HomeAssistant,
    gen: int,
    mock_block_device: Mock,
    mock_rpc_device: Mock,
) -> None:
    """Test reconfiguration flow failed."""
    entry = MockConfigEntry(
        domain="shelly",
        unique_id="test-mac",
        data={CONF_HOST: "0.0.0.0", CONF_GEN: gen},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "another-mac",
            "type": MODEL_1,
            "auth": False,
            "gen": gen,
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "another_device"


@pytest.mark.parametrize(
    ("exc", "base_error"),
    [
        (DeviceConnectionError, "cannot_connect"),
        (CustomPortNotSupported, "custom_port_not_supported"),
    ],
)
async def test_reconfigure_with_exception(
    hass: HomeAssistant,
    exc: Exception,
    base_error: str,
    mock_rpc_device: Mock,
) -> None:
    """Test reconfiguration flow when an exception is raised."""
    entry = MockConfigEntry(
        domain="shelly", unique_id="test-mac", data={CONF_HOST: "0.0.0.0", CONF_GEN: 2}
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch("homeassistant.components.shelly.config_flow.get_info", side_effect=exc):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["errors"] == {"base": base_error}

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={"mac": "test-mac", "type": MODEL_1, "auth": False, "gen": 2},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "10.10.10.10", CONF_PORT: 99},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "10.10.10.10", CONF_PORT: 99, CONF_GEN: 2}


async def test_zeroconf_rejects_ipv6(hass: HomeAssistant) -> None:
    """Test zeroconf discovery rejects ipv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("fd00::b27c:63bb:cc85:4ea0"),
            ip_addresses=[ip_address("fd00::b27c:63bb:cc85:4ea0")],
            hostname="mock_hostname",
            name="shelly1pm-12345",
            port=None,
            properties={ATTR_PROPERTIES_ID: "shelly1pm-12345"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ipv6_not_supported"


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_zeroconf_wrong_device_name(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test zeroconf discovery with mismatched device name."""

    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value={
            "mac": "test-mac",
            "model": MODEL_PLUS_2PM,
            "auth": False,
            "gen": 2,
        },
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=DISCOVERY_INFO_WRONG_NAME,
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}
        context = next(
            flow["context"]
            for flow in hass.config_entries.flow.async_progress()
            if flow["flow_id"] == result["flow_id"]
        )
        assert context["title_placeholders"]["name"] == "Shelly Plus 2PM [DDEEFF]"
        assert context["confirm_only"] is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert result["result"].unique_id == "test-mac"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test bluetooth discovery and complete provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"]["name"] == "ShellyPlus2PM-C049EF8873E8"

    # Confirm
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Select network and enter password to provision
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning happens in background, shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning by configuring the progress step
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Provisioning should complete and create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_provisioning_clears_match_history(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test bluetooth provisioning clears match history at discovery start and after successful provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO_FOR_CLEAR_TEST)

    with patch(
        "homeassistant.components.shelly.config_flow.async_clear_address_from_match_history",
    ) as mock_clear:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=BLE_DISCOVERY_INFO_FOR_CLEAR_TEST,
            context={"source": config_entries.SOURCE_BLUETOOTH},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "bluetooth_confirm"

        # Confirm
        with patch(
            "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
            return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {}
            )

        # Reset mock to only count calls during provisioning
        mock_clear.reset_mock()

        # Select network and enter password to provision
        with (
            patch(
                "homeassistant.components.shelly.config_flow.async_provision_wifi",
            ),
            patch(
                "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
                return_value=("1.1.1.1", 80),
            ),
            patch(
                "homeassistant.components.shelly.config_flow.get_info",
                return_value=MOCK_DEVICE_INFO,
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
            )

            # Provisioning happens in background, shows progress
            assert result["type"] is FlowResultType.SHOW_PROGRESS
            await hass.async_block_till_done()

            # Complete provisioning by configuring the progress step
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Provisioning should complete and create entry
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "AABBCCDDEE00"

        # Verify match history was cleared once during provisioning
        # Only count calls with our test device's address to avoid interference from other tests
        our_device_calls = [
            call
            for call in mock_clear.call_args_list
            if len(call.args) > 1
            and call.args[1] == BLE_DISCOVERY_INFO_FOR_CLEAR_TEST.address
        ]
        assert our_device_calls
        mock_clear.assert_called_with(hass, BLE_DISCOVERY_INFO_FOR_CLEAR_TEST.address)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_discovery_no_rpc_over_ble(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery without RPC-over-BLE enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO_NO_RPC,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


async def test_bluetooth_factory_reset_rediscovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test device can be rediscovered after factory reset when RPC-over-BLE is re-enabled."""
    # First discovery: device is already provisioned (no RPC-over-BLE)
    # Inject the device without RPC so it's in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO_NO_RPC)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO_NO_RPC,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Should abort because RPC-over-BLE is not enabled
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"

    # Simulate factory reset: device now advertises with RPC-over-BLE enabled
    # Inject the updated advertisement
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    # Second discovery: device after factory reset (RPC-over-BLE now enabled)
    # Wait for automatic discovery to happen
    await hass.async_block_till_done()

    # Find the flow that was automatically created
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]

    # Should successfully start config flow since match history was cleared
    assert result["step_id"] == "bluetooth_confirm"
    assert (
        result["context"]["title_placeholders"]["name"] == "ShellyPlus2PM-C049EF8873E8"
    )

    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Select network and enter password to provision
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning happens in background
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Provisioning should complete and create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_discovery_invalid_name(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery with invalid device name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO_INVALID_NAME,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_discovery_info"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_discovery_mac_in_manufacturer_data(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery with MAC in manufacturer data (newer devices)."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(
        hass, BLE_DISCOVERY_INFO_MAC_IN_MANUFACTURER_DATA
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO_MAC_IN_MANUFACTURER_DATA,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Should successfully extract MAC from manufacturer data
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    # MAC from manufacturer data: 70d6c297bacc (reversed) = CC:BA:97:C2:D6:70 = CCBA97C2D670
    # Model ID 0x1030 = Shelly 1 Mini Gen4
    # Device name should use model name from model ID: Shelly1MiniGen4-<MAC>
    assert result["description_placeholders"]["name"] == "Shelly1MiniGen4-CCBA97C2D670"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_discovery_mac_unknown_model(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery with MAC but unknown model ID."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO_MAC_UNKNOWN_MODEL)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO_MAC_UNKNOWN_MODEL,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Should successfully extract MAC from manufacturer data
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    # MAC from manufacturer data: 70d6c297bacc (reversed) = CC:BA:97:C2:D6:70 = CCBA97C2D670
    # Model ID 0x9999 is unknown - should fall back to generic "Shelly-<MAC>"
    assert result["description_placeholders"]["name"] == "Shelly-CCBA97C2D670"


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery when device is already configured."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C049EF8873E8",  # MAC from device name - uppercase no colons
        data={
            CONF_HOST: "1.1.1.1",
            CONF_MODEL: MODEL_PLUS_2PM,
            CONF_SLEEP_PERIOD: 0,
            CONF_GEN: 2,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_already_configured_clears_match_history(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery clears match history when device already configured."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C049EF8873E8",  # MAC from device name - uppercase no colons
        data={
            CONF_HOST: "1.1.1.1",
            CONF_MODEL: MODEL_PLUS_2PM,
            CONF_SLEEP_PERIOD: 0,
            CONF_GEN: 2,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.shelly.config_flow.async_clear_address_from_match_history"
    ) as mock_clear:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=BLE_DISCOVERY_INFO,
            context={"source": config_entries.SOURCE_BLUETOOTH},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify match history was cleared to allow rediscovery if factory reset
    mock_clear.assert_called_once_with(hass, BLE_DISCOVERY_INFO.address)


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_discovery_no_ble_device(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery when BLE device cannot be found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO_NO_DEVICE,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_wifi_scan_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test WiFi scan via BLE."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm BLE provisioning and trigger wifi scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[
            {"ssid": "Network1", "rssi": -50, "auth": 2},
            {"ssid": "Network2", "rssi": -60, "auth": 3},
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi_scan"
    # Check that SSIDs are in the selector options
    assert "data_schema" in result

    # Select network and enter password to complete flow
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "Network1", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_wifi_scan_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test WiFi scan failure via BLE."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and trigger wifi scan that fails
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=DeviceConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi_scan_failed"

    # Test retry and complete flow
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "Network1", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi_scan"

    # Select network and enter password to complete provisioning
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test name"),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "Network1", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_wifi_scan_ble_not_permitted(
    hass: HomeAssistant,
) -> None:
    """Test WiFi scan when BLE is not permitted (cloud bound device)."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and trigger wifi scan that fails with permission error
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=DeviceConnectionError("Writing is not permitted"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ble_not_permitted"


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_wifi_credentials_and_provision_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test successful WiFi provisioning via BLE."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm BLE provisioning and scan for WiFi networks
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[
            {"ssid": "MyNetwork", "rssi": -50, "auth": 2},
        ],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi_scan"

    # Select network and enter password to provision
    mock_device = create_mock_rpc_device("Test name")

    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
        ) as mock_provision,
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Should show progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS

        # Wait for provision task to complete
        await hass.async_block_till_done()

        # Complete provisioning
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should create entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert mock_provision.call_count == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_wifi_provision_failure(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test WiFi provisioning failure via BLE."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision fails
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
            side_effect=DeviceConnectionError,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Provisioning failed, get the result
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision_failed"

    # Test retry - go back to wifi scan and complete successfully
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wifi_scan"

    # Provision succeeds this time
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bluetooth_wifi_scan_unexpected_exception(
    hass: HomeAssistant,
) -> None:
    """Test unexpected exception during WiFi scan."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and trigger wifi scan that raises unexpected exception
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_provision_unexpected_exception(
    hass: HomeAssistant,
) -> None:
    """Test unexpected exception during provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision raises unexpected exception in background task
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
            side_effect=RuntimeError("Unexpected error"),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Exception in background task causes abort
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_provision_device_connection_error_after_wifi(
    hass: HomeAssistant,
) -> None:
    """Test device connection error after WiFi provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision but get_info fails
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            side_effect=DeviceConnectionError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Provisioning failed due to connection error
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision_failed"

    # User retries but BLE device raises unhandled exception
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=RuntimeError("BLE device unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_rpc_device", "mock_zeroconf")
async def test_bluetooth_provision_requires_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test device requires authentication after WiFi provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision but device requires auth
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value={
                "mac": "C049EF8873E8",
                "model": MODEL_PLUS_2PM,
                "auth": True,  # Auth required
                "gen": 2,
            },
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning, should go to credentials step
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show credentials form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    # Provide password (username is automatically set to "admin" for RPC devices)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert result["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 80,
        CONF_USERNAME: "admin",  # Automatically added for RPC devices
        CONF_PASSWORD: "password",
        CONF_MODEL: MODEL_PLUS_2PM,
        CONF_SLEEP_PERIOD: 0,
        CONF_GEN: 2,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_provision_validate_input_fails(
    hass: HomeAssistant,
) -> None:
    """Test validate_input fails after WiFi provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision but validate_input fails
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            side_effect=DeviceConnectionError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Provisioning failed due to validate_input error
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision_failed"

    # User retries but BLE device raises unhandled exception
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=RuntimeError("BLE device unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_provision_firmware_not_fully_provisioned(
    hass: HomeAssistant,
) -> None:
    """Test device firmware not fully provisioned after WiFi provisioning."""
    # Inject BLE device so it's available in the bluetooth scanner
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision but device has no model (firmware not fully provisioned)
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=create_mock_rpc_device("Test name", model=None),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Should abort due to firmware not fully provisioned
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "firmware_not_fully_provisioned"


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_provision_with_zeroconf_discovery_fast_path(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test zeroconf discovery arrives during WiFi provisioning (fast path - line 551)."""
    # Inject BLE device
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Patch async_provision_wifi to trigger zeroconf discovery
    async def mock_provision_wifi(*args, **kwargs):
        """Mock provision that triggers zeroconf discovery."""
        # Trigger zeroconf discovery for the device
        await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZeroconfServiceInfo(
                ip_address=ip_address("1.1.1.1"),
                ip_addresses=[ip_address("1.1.1.1")],
                hostname="shelly2pm-c049ef8873e8.local.",
                name="shelly2pm-c049ef8873e8",
                port=80,
                properties={"gen": "2"},
                type="_http._tcp.local.",
            ),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )
        # Ensure the zeroconf discovery completes before returning
        await hass.async_block_till_done()

    # Mock device for secure device feature
    mock_device = create_mock_rpc_device("Test name")

    with (
        patch(
            "homeassistant.components.shelly.config_flow.PROVISIONING_TIMEOUT",
            10,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_provision_wifi",
            side_effect=mock_provision_wifi,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Complete provisioning with zeroconf discovery received (fast path)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert result["title"] == "Test name"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_zeroconf")
async def test_bluetooth_provision_timeout_active_lookup_fails(
    hass: HomeAssistant,
) -> None:
    """Test WiFi provisioning times out and active lookup fails (lines 545-547)."""
    # Inject BLE device
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Provision WiFi but no zeroconf discovery arrives, and active lookup fails
    with (
        patch(
            "homeassistant.components.shelly.config_flow.PROVISIONING_TIMEOUT",
            0.01,  # Short timeout to trigger timeout path
        ),
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,  # Active lookup fails
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Timeout occurs, active lookup fails, provision unsuccessful
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show provision_failed form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision_failed"

    # User aborts after failure
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=RuntimeError("BLE device unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_bluetooth_provision_timeout_ble_fallback_succeeds(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test WiFi provisioning times out, active lookup fails, but BLE fallback succeeds."""
    # Inject BLE device
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Mock device for BLE status query
    mock_ble_status_device = AsyncMock()
    mock_ble_status_device.status = {"wifi": {"sta_ip": "192.168.1.100"}}

    # Mock device for secure device feature
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.name = "Test name"
    mock_device.status = {"sys": {}}
    mock_device.xmod_info = {}
    mock_device.shelly = {"model": MODEL_PLUS_2PM}
    mock_device.wifi_setconfig = AsyncMock(return_value={})
    mock_device.ble_setconfig = AsyncMock(return_value={"restart_required": False})
    mock_device.shutdown = AsyncMock()

    # Confirm and scan, then select network and enter password
    # Provision WiFi but no zeroconf discovery arrives, active lookup fails, BLE fallback succeeds
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
            return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
        ),
        patch(
            "homeassistant.components.shelly.config_flow.PROVISIONING_TIMEOUT",
            0.01,  # Short timeout to trigger timeout path
        ),
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,  # Active lookup fails
        ),
        patch(
            "homeassistant.components.shelly.config_flow.ble_rpc_device",
        ) as mock_ble_rpc,
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        # Configure BLE RPC mock to return device with IP
        mock_ble_rpc.return_value.__aenter__.return_value = mock_ble_status_device

        # Scan for networks
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        # Select network and enter password in single step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Timeout occurs, active lookup fails, but BLE fallback gets IP
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should create entry successfully with IP from BLE
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test name"
    assert result["data"][CONF_HOST] == "192.168.1.100"
    assert result["data"][CONF_PORT] == DEFAULT_HTTP_PORT


async def test_bluetooth_provision_timeout_ble_fallback_fails(
    hass: HomeAssistant,
) -> None:
    """Test WiFi provisioning times out, active lookup fails, and BLE fallback also fails."""
    # Inject BLE device
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan, select network and enter password
    # Provision WiFi but no zeroconf discovery, active lookup fails, BLE fallback fails
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
            return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
        ),
        patch(
            "homeassistant.components.shelly.config_flow.PROVISIONING_TIMEOUT",
            0.01,  # Short timeout to trigger timeout path
        ),
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,  # Active lookup fails
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_get_ip_from_ble",
            return_value=None,  # BLE fallback also fails
        ),
    ):
        # Scan for networks
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        # Select network and enter password in single step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Timeout occurs, both active lookup and BLE fallback fail
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show provision_failed form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision_failed"

    # User aborts after failure
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=RuntimeError("BLE device unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_bluetooth_provision_timeout_ble_exception(
    hass: HomeAssistant,
) -> None:
    """Test WiFi provisioning times out, active lookup fails, and BLE raises exception."""
    # Inject BLE device
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm and scan, select network and enter password
    # Provision WiFi but no zeroconf discovery, active lookup fails, BLE raises exception
    with (
        patch(
            "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
            return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
        ),
        patch(
            "homeassistant.components.shelly.config_flow.PROVISIONING_TIMEOUT",
            0.01,  # Short timeout to trigger timeout path
        ),
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=None,  # Active lookup fails
        ),
        patch(
            "homeassistant.components.shelly.config_flow.ble_rpc_device",
            side_effect=DeviceConnectionError,  # BLE raises exception
        ),
    ):
        # Scan for networks
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        # Select network and enter password in single step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )

        # Provisioning shows progress
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        await hass.async_block_till_done()

        # Timeout occurs, both active lookup and BLE fallback fail (exception)
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show provision_failed form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "provision_failed"

    # User aborts after failure
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        side_effect=RuntimeError("BLE device unavailable"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_bluetooth_provision_secure_device_both_enabled(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test provisioning with both AP and BLE disable enabled (default)."""
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm with both switches enabled (default)
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"disable_ap": True, "disable_ble_rpc": True},
        )

    # Provision and verify security calls
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.wifi_setconfig = AsyncMock(return_value={})
    mock_device.ble_setconfig = AsyncMock(return_value={"restart_required": False})
    mock_device.shutdown = AsyncMock()

    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify entry created
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify security calls were made
    mock_device.wifi_setconfig.assert_called_once_with(ap_enable=False)
    mock_device.ble_setconfig.assert_called_once_with(enable=True, enable_rpc=False)
    assert mock_device.shutdown.called


async def test_bluetooth_provision_secure_device_both_disabled(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test provisioning with both AP and BLE disable disabled."""
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm with both switches disabled
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"disable_ap": False, "disable_ble_rpc": False},
        )

    # Provision - with both disabled, secure device method should not create device
    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify entry created (secure device call is skipped when both disabled)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_bluetooth_provision_secure_device_only_ap_disabled(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test provisioning with only AP disable enabled."""
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm with only AP disable
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"disable_ap": True, "disable_ble_rpc": False},
        )

    # Provision and verify only AP disabled
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.wifi_setconfig = AsyncMock(return_value={})
    mock_device.shutdown = AsyncMock()

    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify entry created
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify only wifi_setconfig was called
    mock_device.wifi_setconfig.assert_called_once_with(ap_enable=False)
    assert mock_device.shutdown.called


async def test_bluetooth_provision_secure_device_only_ble_disabled(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test provisioning with only BLE disable enabled."""
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm with only BLE disable
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"disable_ap": False, "disable_ble_rpc": True},
        )

    # Provision and verify only BLE disabled
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.ble_setconfig = AsyncMock(return_value={"restart_required": False})
    mock_device.shutdown = AsyncMock()

    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify entry created
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify only ble_setconfig was called
    mock_device.ble_setconfig.assert_called_once_with(enable=True, enable_rpc=False)
    assert mock_device.shutdown.called


async def test_bluetooth_provision_secure_device_with_restart_required(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test provisioning when BLE disable requires restart."""
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm with both enabled
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"disable_ap": True, "disable_ble_rpc": True},
        )

    # Provision and verify restart is triggered
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.wifi_setconfig = AsyncMock(return_value={})
    mock_device.ble_setconfig = AsyncMock(return_value={"restart_required": True})
    mock_device.trigger_reboot = AsyncMock()
    mock_device.shutdown = AsyncMock()

    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify entry created
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify restart was triggered and shutdown called
    mock_device.trigger_reboot.assert_called_once_with(delay_ms=1000)
    assert mock_device.shutdown.called


async def test_bluetooth_provision_secure_device_fails_gracefully(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test provisioning succeeds even when secure device calls fail."""
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    # Confirm with both enabled
    with patch(
        "homeassistant.components.shelly.config_flow.async_scan_wifi_networks",
        return_value=[{"ssid": "MyNetwork", "rssi": -50, "auth": 2}],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"disable_ap": True, "disable_ble_rpc": True},
        )

    # Provision with security calls failing - wifi_setconfig will fail
    mock_device = AsyncMock()
    mock_device.initialize = AsyncMock()
    mock_device.wifi_setconfig = AsyncMock(side_effect=RpcCallError("RPC call failed"))
    mock_device.shutdown = AsyncMock()

    with (
        patch("homeassistant.components.shelly.config_flow.async_provision_wifi"),
        patch(
            "homeassistant.components.shelly.config_flow.async_lookup_device_by_name",
            return_value=("1.1.1.1", 80),
        ),
        patch(
            "homeassistant.components.shelly.config_flow.get_info",
            return_value=MOCK_DEVICE_INFO,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.RpcDevice.create",
            return_value=mock_device,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SSID: "MyNetwork", CONF_PASSWORD: "my_password"},
        )
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Verify entry still created despite secure device failure
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"


async def test_zeroconf_aborts_idle_ble_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_setup: AsyncMock,
) -> None:
    """Test zeroconf discovery aborts idle BLE flow (lines 316-321)."""
    # Start BLE discovery flow and leave it idle at bluetooth_confirm
    inject_bluetooth_service_info_bleak(hass, BLE_DISCOVERY_INFO)

    ble_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=BLE_DISCOVERY_INFO,
        context={"source": config_entries.SOURCE_BLUETOOTH},
    )

    assert ble_result["type"] is FlowResultType.FORM
    assert ble_result["step_id"] == "bluetooth_confirm"
    ble_flow_id = ble_result["flow_id"]

    # Now start zeroconf discovery for the same device - should abort BLE flow
    with patch(
        "homeassistant.components.shelly.config_flow.get_info",
        return_value=MOCK_DEVICE_INFO,
    ):
        zeroconf_result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data=ZeroconfServiceInfo(
                ip_address=ip_address("1.1.1.1"),
                ip_addresses=[ip_address("1.1.1.1")],
                hostname="shelly2pm-c049ef8873e8.local.",
                name="shelly2pm-c049ef8873e8",
                port=80,
                properties={"gen": "2"},
                type="_http._tcp.local.",
            ),
            context={"source": config_entries.SOURCE_ZEROCONF},
        )

    # Verify BLE flow was aborted
    flows = hass.config_entries.flow.async_progress()
    assert not any(flow["flow_id"] == ble_flow_id for flow in flows)

    # Complete zeroconf flow
    assert zeroconf_result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        zeroconf_result["flow_id"], {}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "C049EF8873E8"
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
