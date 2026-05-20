"""Tests for the RYSE BLE config flow."""

from __future__ import annotations

import time
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
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
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
    rssi=RSSI_VALUE,
    tx_power=None,
    platform_data=(),
)


BLE_DEVICE = BLEDevice(
    address=DEVICE_ADDRESS,
    name=DEVICE_NAME,
    details={},
    rssi=RSSI_VALUE,
)

DISCOVERY_INFO = BluetoothServiceInfoBleak(
    name=DEVICE_NAME,
    address=DEVICE_ADDRESS,
    rssi=-40,
    manufacturer_data={},
    service_data={},
    service_uuids=["0000fff0-0000-1000-8000-00805f9b34fb"],
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
def mock_pairing():
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
def discovery():
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
        (Exception, "unknown"),
        (None, "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("discovery")
async def test_async_step_user_errors(
    hass: HomeAssistant,
    mock_pairing,
    raise_error,
    expected_error,
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
async def test_async_step_user_no_devices_found(hass: HomeAssistant, discovery) -> None:
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
        (Exception, "unknown"),
        (None, "cannot_connect"),
    ],
)
async def test_async_step_bluetooth_errors(
    hass: HomeAssistant,
    mock_pairing,
    raise_error,
    error_text,
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
