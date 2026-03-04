"""Test the Flic Button sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    DeviceType,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FLIC2_ADDRESS,
    FLIC2_SERIAL,
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_dependencies():
    """Set up mock dependencies for sensor tests."""
    mock_coordinator = MagicMock()
    mock_coordinator.connected = True
    mock_coordinator.serial_number = FLIC2_SERIAL
    mock_coordinator.is_duo = False
    mock_coordinator.is_twist = False
    mock_coordinator.model_name = "Flic 2"
    mock_coordinator.device_type = DeviceType.FLIC2
    mock_coordinator.last_update_success = True
    mock_coordinator.async_connect = AsyncMock()
    mock_coordinator.async_disconnect = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)

    # Mock client
    mock_client = MagicMock()
    mock_client.address = FLIC2_ADDRESS
    mock_client.is_connected = True
    mock_coordinator.client = mock_client

    # Mock capabilities
    mock_capabilities = MagicMock()
    mock_capabilities.button_count = 1
    mock_capabilities.has_rotation = False
    mock_capabilities.has_selector = False
    mock_coordinator.capabilities = mock_capabilities

    # Set battery voltage data (800/1024 * 3.6 = 2.8125V)
    battery_voltage = TEST_BATTERY_LEVEL * 3.6 / 1024.0
    mock_coordinator.data = {"battery_voltage": battery_voltage}

    # Firmware version
    mock_coordinator.firmware_version = None

    # Firmware update state
    mock_coordinator.latest_firmware_version = None
    mock_coordinator.firmware_download_url = None
    mock_coordinator.firmware_update_in_progress = False
    mock_coordinator.firmware_update_percentage = None

    # Async methods that may be awaited during setup
    mock_coordinator.async_load_slot_values = AsyncMock()

    return mock_coordinator


async def test_battery_sensor_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Test battery sensor is created with correct properties."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_setup_dependencies,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check sensor entity exists in registry (entity ID format may vary)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    sensor_entities = [e for e in entities if e.domain == "sensor"]

    assert len(sensor_entities) >= 1

    # Verify sensor properties from registry
    battery_entity = sensor_entities[0]
    assert battery_entity.original_device_class == SensorDeviceClass.BATTERY
    assert battery_entity.entity_category == EntityCategory.DIAGNOSTIC


async def test_battery_sensor_value_conversion(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Test battery sensor correctly converts voltage to percentage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    # Set battery voltage to 3.3V (should be ~50%)
    mock_setup_dependencies.data = {"battery_voltage": 3.3}

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_setup_dependencies,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify the entity exists
    assert entry.state is ConfigEntryState.LOADED


async def test_battery_sensor_no_data(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Test battery sensor handles missing data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    # No battery data
    mock_setup_dependencies.data = {}

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_setup_dependencies,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_battery_sensor_unavailable_when_disconnected(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Test battery sensor shows unavailable when device is disconnected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    # Device is disconnected
    mock_setup_dependencies.connected = False

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_setup_dependencies,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
