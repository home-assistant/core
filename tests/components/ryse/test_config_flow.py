"""Tests for the RYSE BLE config flow."""

from __future__ import annotations

from collections.abc import Generator
import time
from unittest.mock import MagicMock, patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError
import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.ryse.const import DOMAIN, MANUFACTURER_ID
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DEVICE_NAME = "RYSE Shade"
DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
RSSI_VALUE = -40
PAIRING_MANUFACTURER_DATA = {MANUFACTURER_ID: b"\xcc\x64\x62\x64"}
IDLE_MANUFACTURER_DATA = {MANUFACTURER_ID: b"\x8c\x64\x62\x64"}

ADVERTISEMENT_DATA = AdvertisementData(
    local_name=DEVICE_NAME,
    manufacturer_data=PAIRING_MANUFACTURER_DATA,
    service_data={},
    service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
    rssi=RSSI_VALUE,
    tx_power=None,
    platform_data=(),
)

BLE_DEVICE = BLEDevice(DEVICE_ADDRESS, DEVICE_NAME, {})

DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name=DEVICE_NAME,
    address=DEVICE_ADDRESS,
    rssi=-40,
    manufacturer_data=PAIRING_MANUFACTURER_DATA,
    service_data={},
    service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
    source="local",
    device=BLE_DEVICE,
    advertisement=ADVERTISEMENT_DATA,
    time=time.time(),
    connectable=True,
    tx_power=-127,
)


def _idle_discovery() -> BluetoothServiceInfoBleak:
    """Return a RYSE advertisement without the PAIR flag."""
    idle_device = BLEDevice(DEVICE_ADDRESS, DEVICE_NAME, {})
    return BluetoothServiceInfoBleak(
        name=DEVICE_NAME,
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data=IDLE_MANUFACTURER_DATA,
        service_data={},
        service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
        source="local",
        device=idle_device,
        advertisement=AdvertisementData(
            local_name=DEVICE_NAME,
            manufacturer_data=IDLE_MANUFACTURER_DATA,
            service_data={},
            service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
            rssi=RSSI_VALUE,
            tx_power=None,
            platform_data=(),
        ),
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )


def _proxy_discovery() -> BluetoothServiceInfoBleak:
    """Return a pairing advertisement seen only through a Bluetooth proxy."""
    proxy_device = BLEDevice(DEVICE_ADDRESS, DEVICE_NAME, {})
    return BluetoothServiceInfoBleak(
        name=DEVICE_NAME,
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data=PAIRING_MANUFACTURER_DATA,
        service_data={},
        service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
        source="aa:bb:cc:dd:ee:00",
        device=proxy_device,
        advertisement=ADVERTISEMENT_DATA,
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )


USER_INPUT = {CONF_ADDRESS: DEVICE_ADDRESS}

PAIRING_ERRORS = [
    (Exception("boom"), "unexpected_error"),
    (TimeoutError("timeout"), "cannot_connect"),
    (OSError("os error"), "cannot_connect"),
    (EOFError("eof"), "cannot_connect"),
    (BleakError("bleak error"), "cannot_connect"),
    (False, "cannot_connect"),
]


@pytest.fixture(autouse=True)
def mock_last_service_info() -> Generator[MagicMock]:
    """Use the stored discovery advertisement when no scanner cache is present."""
    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_last_service_info",
            return_value=None,
        ) as mock,
        patch(
            "homeassistant.components.ryse.config_flow.async_clear_address_from_match_history",
        ),
    ):
        yield mock


@pytest.fixture
def discovery() -> Generator[MagicMock]:
    """Mock async_discovered_service_info."""
    with patch(
        "homeassistant.components.ryse.config_flow.async_discovered_service_info",
        autospec=True,
    ) as mock_discovery:
        mock_discovery.return_value = [DISCOVERY_INFO]
        yield mock_discovery


@pytest.mark.usefixtures("discovery")
async def test_async_step_user_success(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test user flow succeeds and creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
    mock_device.unpair.assert_awaited_once()


@pytest.mark.parametrize(("pair_result", "expected_error"), PAIRING_ERRORS)
@pytest.mark.usefixtures("discovery")
async def test_async_step_user_errors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    pair_result: Exception | bool,
    expected_error: str,
) -> None:
    """Test errors during user pairing can be recovered from."""
    mock_device.pair.side_effect = [pair_result, True]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS


async def test_async_step_user_keeps_device_after_pairing_error(
    hass: HomeAssistant,
    mock_device: MagicMock,
    discovery: MagicMock,
) -> None:
    """Test a pairing error keeps the selected device even if it leaves pairing mode."""
    mock_device.pair.side_effect = [False, True]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    discovery.return_value = [_idle_discovery()]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ADDRESS


@pytest.mark.usefixtures("discovery")
async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant,
) -> None:
    """Test that we abort if the device gets added in another flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ADDRESS,
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_user_no_devices_found(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we abort when no devices are discovered."""
    discovery.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test Bluetooth discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
    mock_device.unpair.assert_awaited_once()


@pytest.mark.parametrize(("pair_result", "error_text"), PAIRING_ERRORS)
async def test_async_step_bluetooth_errors(
    hass: HomeAssistant,
    mock_device: MagicMock,
    pair_result: Exception | bool,
    error_text: str,
) -> None:
    """Test Bluetooth discovery confirm errors can be recovered from."""
    mock_device.pair.side_effect = [pair_result, True]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_text}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS


async def test_async_step_bluetooth_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test abort if device already configured before bluetooth discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ADDRESS,
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("discovery")
async def test_async_step_user_skips_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test that we skip already configured devices in user flow discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ADDRESS,
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_skips_nameless_device(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip nameless devices in user flow discovery."""
    nameless_device = BLEDevice(DEVICE_ADDRESS, None, {})
    nameless_discovery = BluetoothServiceInfoBleak(
        name=None,
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data=PAIRING_MANUFACTURER_DATA,
        service_data={},
        service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
        source="local",
        device=nameless_device,
        advertisement=ADVERTISEMENT_DATA,
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )
    discovery.return_value = [nameless_discovery]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_skips_non_pairing_device(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip devices that are not advertising pairing mode."""
    discovery.return_value = [_idle_discovery()]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("discovery")
async def test_async_step_user_skips_unmatched_device(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip devices that do not match RYSE pairing advertisements."""
    ble_device = BLEDevice(DEVICE_ADDRESS, "Generic Device", {})
    unmatched_discovery = BluetoothServiceInfoBleak(
        name="Generic Device",
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data={999: b"\x01"},
        service_data={},
        service_uuids=["00001234-0000-1000-8000-00805f9b34fb"],
        source="local",
        device=ble_device,
        advertisement=AdvertisementData(
            local_name="Generic Device",
            manufacturer_data={999: b"\x01"},
            service_data={},
            service_uuids=["00001234-0000-1000-8000-00805f9b34fb"],
            rssi=-40,
            tx_power=None,
            platform_data=(),
        ),
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )
    discovery.return_value = [unmatched_discovery]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_skips_proxy_source(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip devices seen only through a Bluetooth proxy."""
    discovery.return_value = [_proxy_discovery()]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_not_in_pairing_mode(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test idle advertisements are not shown as discoveries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_idle_discovery(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_in_pairing_mode"
    mock_device.pair.assert_not_called()


async def test_async_step_bluetooth_rejects_proxy_source(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test proxy-only discoveries are aborted before the confirmation form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_proxy_discovery(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_local_source"
    mock_device.pair.assert_not_called()


async def test_async_step_bluetooth_pairing_overrides_stale_idle(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_last_service_info: MagicMock,
) -> None:
    """Test a PAIR advertisement is shown even if the scanner cache is still idle."""
    mock_last_service_info.return_value = _idle_discovery()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    mock_device.pair.assert_not_called()


async def test_async_step_bluetooth_left_pairing_mode(
    hass: HomeAssistant,
    mock_device: MagicMock,
    mock_last_service_info: MagicMock,
) -> None:
    """Test we refuse to pair if the shade leaves pairing mode before confirm."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    mock_last_service_info.return_value = _idle_discovery()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_pairing_mode"}
    mock_device.pair.assert_not_called()


async def test_async_step_bluetooth_fallback_name(
    hass: HomeAssistant, mock_device: MagicMock
) -> None:
    """Test Bluetooth discovery flow fallback name when service info name is empty."""
    nameless_device = BLEDevice(DEVICE_ADDRESS, "", {})
    nameless_discovery = BluetoothServiceInfoBleak(
        name="",
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data=PAIRING_MANUFACTURER_DATA,
        service_data={},
        service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
        source="local",
        device=nameless_device,
        advertisement=ADVERTISEMENT_DATA,
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=nameless_discovery,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": "RYSE device"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RYSE device"
    assert result["data"] == {}
    assert result["result"].unique_id == DEVICE_ADDRESS
    mock_device.pair.assert_awaited_once()
