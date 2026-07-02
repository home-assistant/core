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
from homeassistant.components.ryse.const import DOMAIN
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

DEVICE_NAME = "RYSE Shade"
DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
RSSI_VALUE = -40

ADVERTISEMENT_DATA = AdvertisementData(
    local_name=DEVICE_NAME,
    manufacturer_data={},
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
    manufacturer_data={},
    service_data={},
    service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
    source="local",
    device=BLE_DEVICE,
    advertisement=ADVERTISEMENT_DATA,
    time=time.time(),
    connectable=True,
    tx_power=-127,
)

USER_INPUT = {CONF_ADDRESS: DEVICE_ADDRESS}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pairing() -> Generator[tuple[MagicMock, MagicMock]]:
    """Mock pair_with_ble_device + is_pairing_ryse_device."""
    with (
        patch(
            "homeassistant.components.ryse.config_flow.pair_with_ble_device",
            autospec=True,
        ) as mock_pair,
        patch(
            "homeassistant.components.ryse.config_flow.is_pairing_ryse_device",
            autospec=True,
        ) as mock_is_pair,
    ):
        mock_pair.return_value = True
        mock_is_pair.return_value = True
        yield mock_pair, mock_is_pair


@pytest.fixture
def discovery() -> Generator[MagicMock]:
    """Mock async_discovered_service_info."""
    with patch(
        "homeassistant.components.ryse.config_flow.async_discovered_service_info",
        autospec=True,
    ) as mock_discovery:
        mock_discovery.return_value = [DISCOVERY_INFO]
        yield mock_discovery


# ---------------------------------------------------------------------------
# USER STEP TESTS
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("discovery", "mock_pairing")
async def test_async_step_user_success(hass: HomeAssistant) -> None:
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


@pytest.mark.parametrize(
    ("raise_error", "expected_error"),
    [
        (Exception("boom"), "unexpected_error"),
        (TimeoutError("timeout"), "cannot_connect"),
        (OSError("os error"), "cannot_connect"),
        (BleakError("bleak error"), "cannot_connect"),
        (None, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("discovery")
async def test_async_step_user_errors(
    hass: HomeAssistant,
    mock_pairing: tuple[MagicMock, MagicMock],
    raise_error: Exception | None,
    expected_error: str,
) -> None:
    """Test errors during user pairing."""

    mock_pair, _ = mock_pairing
    mock_pair.side_effect = raise_error
    if raise_error is None:
        mock_pair.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.usefixtures("discovery", "mock_pairing")
async def test_async_step_user_device_added_between_steps(
    hass: HomeAssistant,
) -> None:
    """Test that we abort if the device gets added in another flow."""

    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # Add entry manually (simulating another flow creating it)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ADDRESS,
        data={},
    )
    entry.add_to_hass(hass)

    # Continue previous flow → must abort
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_pairing")
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


# ---------------------------------------------------------------------------
# BLUETOOTH DISCOVERY TESTS
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_bluetooth(hass: HomeAssistant) -> None:
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


@pytest.mark.parametrize(
    ("raise_error", "error_text"),
    [
        (Exception("boom"), "unexpected_error"),
        (TimeoutError("timeout"), "cannot_connect"),
        (OSError("os error"), "cannot_connect"),
        (BleakError("bleak error"), "cannot_connect"),
        (None, "cannot_connect"),
    ],
)
async def test_async_step_bluetooth_errors(
    hass: HomeAssistant,
    mock_pairing: tuple[MagicMock, MagicMock],
    raise_error: Exception | None,
    error_text: str,
) -> None:
    """Test Bluetooth discovery confirm error handling."""

    mock_pair, _ = mock_pairing
    mock_pair.side_effect = raise_error
    if raise_error is None:
        mock_pair.return_value = False

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


@pytest.mark.usefixtures("mock_pairing")
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


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_user_skips_already_configured(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip already configured devices in user flow discovery."""
    # Add the device as already configured
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


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_user_skips_nameless_device(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip nameless devices in user flow discovery."""
    nameless_device = BLEDevice(DEVICE_ADDRESS, None, {})
    nameless_discovery = BluetoothServiceInfoBleak(
        name=None,
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data={},
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
    hass: HomeAssistant, discovery: MagicMock, mock_pairing: tuple[MagicMock, MagicMock]
) -> None:
    """Test that we skip devices that are not in pairing mode."""
    _, mock_is_pair = mock_pairing
    mock_is_pair.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_user_filter_matching_manufacturer_id(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we discover devices matching the RYSE manufacturer ID."""
    ble_device = BLEDevice(DEVICE_ADDRESS, "Generic Device", {})
    matching_discovery = BluetoothServiceInfoBleak(
        name="Generic Device",
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data={1033: b"\x01\x02"},
        service_data={},
        service_uuids=[],
        source="local",
        device=ble_device,
        advertisement=AdvertisementData(
            local_name="Generic Device",
            manufacturer_data={1033: b"\x01\x02"},
            service_data={},
            service_uuids=[],
            rssi=-40,
            tx_power=None,
            platform_data=(),
        ),
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )
    discovery.return_value = [matching_discovery]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_user_filter_matching_service_uuid(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we discover devices matching the custom RYSE service UUID."""
    ble_device = BLEDevice(DEVICE_ADDRESS, "Generic Device", {})
    matching_discovery = BluetoothServiceInfoBleak(
        name="Generic Device",
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data={},
        service_data={},
        service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
        source="local",
        device=ble_device,
        advertisement=AdvertisementData(
            local_name="Generic Device",
            manufacturer_data={},
            service_data={},
            service_uuids=["a72f2800-b0bd-498b-b4cd-4a3901388238"],
            rssi=-40,
            tx_power=None,
            platform_data=(),
        ),
        time=time.time(),
        connectable=True,
        tx_power=-127,
    )
    discovery.return_value = [matching_discovery]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_user_skips_unmatched_device(
    hass: HomeAssistant, discovery: MagicMock
) -> None:
    """Test that we skip devices that do not match any RYSE BLE identifiers."""
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


@pytest.mark.usefixtures("mock_pairing")
async def test_async_step_bluetooth_fallback_name(hass: HomeAssistant) -> None:
    """Test Bluetooth discovery flow fallback name when service info name is empty."""
    nameless_device = BLEDevice(DEVICE_ADDRESS, "", {})
    nameless_discovery = BluetoothServiceInfoBleak(
        name="",
        address=DEVICE_ADDRESS,
        rssi=-40,
        manufacturer_data={},
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


async def test_async_step_user_pairing_check_timeout(
    hass: HomeAssistant, discovery: MagicMock, mock_pairing: tuple[MagicMock, MagicMock]
) -> None:
    """Test handling a timeout when checking if a device is in pairing mode."""
    _, mock_is_pair = mock_pairing
    # Simulate a timeout error inside the async context
    mock_is_pair.side_effect = TimeoutError("Connection timed out")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Because it timed out, the candidate is discarded, leaving no devices
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_pairing_check_unexpected_exception(
    hass: HomeAssistant, discovery: MagicMock, mock_pairing: tuple[MagicMock, MagicMock]
) -> None:
    """Test handling an unexpected exception when checking pairing status."""
    _, mock_is_pair = mock_pairing
    mock_is_pair.side_effect = RuntimeError("Hardware failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Discarded due to exception, leading to no devices found
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
