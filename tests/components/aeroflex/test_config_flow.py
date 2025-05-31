"""Test the Aeroflex config flow."""

import logging
from unittest.mock import AsyncMock, patch

from bleak.backends.device import BLEDevice
import pytest

from homeassistant import config_entries
from homeassistant.components.aeroflex.const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    DOMAIN,
)
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

# Test constants
TEST_DEVICE_ADDRESS = "00:11:22:33:44:55"
TEST_DEVICE_NAME = "Aeroflex Bed"
TEST_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
TEST_CUSTOM_NAME = "Custom Name"
TEST_MY_BED_NAME = "My Aeroflex Bed"


@pytest.fixture(autouse=True)
async def setup_component(hass: HomeAssistant):
    """Set up the component for tests."""
    # Initialize component data structure
    hass.data.setdefault(DOMAIN, {})

    # Mock component setup to avoid actual device connections
    with (
        patch("homeassistant.components.aeroflex.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.aeroflex.async_unload_entry", return_value=True
        ),
    ):
        # Make sure the component is set up
        await hass.async_block_till_done()
        yield
        # Clean up after tests
        hass.data[DOMAIN] = {}


def create_mock_device(name: str = TEST_DEVICE_NAME) -> BLEDevice:
    """Create a mock device."""
    return BLEDevice(
        address=TEST_DEVICE_ADDRESS,
        name=name,
        details={},
        rssi=-60,
        metadata={},
    )


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test we can discover and configure a device."""
    mock_device = create_mock_device()
    service_info = BluetoothServiceInfoBleak(
        name=TEST_DEVICE_NAME,
        address=TEST_DEVICE_ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[TEST_SERVICE_UUID],
        source="local",
        device=mock_device,
        advertisement=AsyncMock(manufacturer_data={}, service_data={}),
        time=0,
        connectable=True,
        tx_power=-127,
    )

    # Use mock to prevent actual discovery
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=service_info,
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": TEST_DEVICE_NAME}

    # Make sure setup works correctly
    with patch(
        "homeassistant.components.aeroflex.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_NAME: TEST_MY_BED_NAME}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_MY_BED_NAME
    assert result2["data"] == {
        CONF_DEVICE_ADDRESS: TEST_DEVICE_ADDRESS,
        CONF_DEVICE_NAME: TEST_MY_BED_NAME,
    }
    assert result2["result"].unique_id == TEST_DEVICE_ADDRESS
    assert len(mock_setup_entry.mock_calls) == 1

    # Clean up entry
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


async def test_bluetooth_discovery_already_setup(hass: HomeAssistant) -> None:
    """Test we can't start a second flow for the same device."""
    mock_device = create_mock_device()
    service_info = BluetoothServiceInfoBleak(
        name=TEST_DEVICE_NAME,
        address=TEST_DEVICE_ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[TEST_SERVICE_UUID],
        source="local",
        device=mock_device,
        advertisement=AsyncMock(manufacturer_data={}, service_data={}),
        time=0,
        connectable=True,
        tx_power=-127,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_ADDRESS,
        data={
            CONF_DEVICE_ADDRESS: TEST_DEVICE_ADDRESS,
            CONF_DEVICE_NAME: TEST_DEVICE_NAME,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=service_info,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_unnamed_device(hass: HomeAssistant) -> None:
    """Test discovery with an unnamed device uses MAC address in name."""
    mock_device = create_mock_device(name=None)
    service_info = BluetoothServiceInfoBleak(
        name=None,
        address=TEST_DEVICE_ADDRESS,
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[TEST_SERVICE_UUID],
        source="local",
        device=mock_device,
        advertisement=AsyncMock(manufacturer_data={}, service_data={}),
        time=0,
        connectable=True,
        tx_power=-127,
    )

    # Use mock to prevent actual discovery
    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=service_info,
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"
    assert result["description_placeholders"] == {"name": TEST_DEVICE_NAME}

    # Make sure setup works correctly
    with patch(
        "homeassistant.components.aeroflex.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NAME: TEST_CUSTOM_NAME},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == TEST_CUSTOM_NAME
    assert result2["data"] == {
        CONF_DEVICE_ADDRESS: TEST_DEVICE_ADDRESS,
        CONF_DEVICE_NAME: TEST_CUSTOM_NAME,
    }
    assert result2["result"].unique_id == TEST_DEVICE_ADDRESS
    assert len(mock_setup_entry.mock_calls) == 1

    # Clean up entry
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
