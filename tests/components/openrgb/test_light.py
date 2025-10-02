"""Tests for the OpenRGB light platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from openrgb.utils import RGBColor
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.openrgb.const import DEFAULT_COLOR, DOMAIN, OpenRGBMode
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def light_only() -> Generator[None]:
    """Enable only the light platform."""
    with patch(
        "homeassistant.components.openrgb.PLATFORMS",
        [Platform.LIGHT],
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure entities are correctly assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={
            (
                DOMAIN,
                f"{mock_config_entry.entry_id}||LEDSTRIP||Test Vendor||Test LED Strip||TEST123||Test Location",
            )
        }
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    # Filter out the server device
    entity_entries = [e for e in entity_entries if e.device_id == device_entry.id]
    assert len(entity_entries) == 1
    assert entity_entries[0].device_id == device_entry.id


async def test_turn_on_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light."""
    # Initialize device in Off mode
    mock_openrgb_device.active_mode = 3

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Verify light is initially off
    state = hass.states.get("light.test_rgb_device")
    assert state
    assert state.state == STATE_OFF

    # Turn on without parameters
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.test_rgb_device"},
        blocking=True,
    )

    # Verify that set_mode was called to restore to Static mode (preferred over Direct)
    mock_openrgb_device.set_mode.assert_called_once_with(OpenRGBMode.STATIC)
    # And set_color was called with default color
    mock_openrgb_device.set_color.assert_called_once_with(
        RGBColor(*DEFAULT_COLOR), True
    )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_color(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light with color."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_rgb_device",
            ATTR_RGB_COLOR: (0, 255, 0),
        },
        blocking=True,
    )

    # Check that set_color was called with green color scaled by brightness
    # Current brightness is 255 (from initial red color), so green should be full
    mock_openrgb_device.set_color.assert_called_once_with(
        RGBColor(red=0, green=255, blue=0), True
    )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_brightness(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light with brightness."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_rgb_device",
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )

    # Check that set_color was called with scaled color by brightness (128/255 = 0.502)
    # Initial color (255, 0, 0) -> HS (0.0, 100.0) -> When applying brightness 128,
    # the V component becomes 50.2%, giving RGB (128, 128, 128) after hs_to_RGB conversion
    mock_openrgb_device.set_color.assert_called_once_with(
        RGBColor(red=128, green=128, blue=128), True
    )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_light_with_effect(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning on the light with effect."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.test_rgb_device",
            ATTR_EFFECT: "Rainbow",
        },
        blocking=True,
    )

    mock_openrgb_device.set_mode.assert_called_once_with("Rainbow")


@pytest.mark.usefixtures("init_integration")
async def test_turn_off_light(
    hass: HomeAssistant,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test turning off the light."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.test_rgb_device"},
        blocking=True,
    )

    # Device supports "Off" mode
    mock_openrgb_device.set_mode.assert_called_with(OpenRGBMode.OFF)


async def test_dynamic_device_addition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test that new devices are added dynamically."""
    mock_config_entry.add_to_hass(hass)

    # Start with one device
    mock_openrgb_client.devices = [mock_openrgb_device]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Check that one light entity exists
    state = hass.states.get("light.test_rgb_device")
    assert state

    # Add a second device
    new_device = MagicMock()
    new_device.id = 1  # Different device ID
    new_device.name = "New RGB Device"
    new_device.type = MagicMock()
    new_device.type.name = "KEYBOARD"
    new_device.metadata = MagicMock()
    new_device.metadata.vendor = "New Vendor"
    new_device.metadata.description = "New Keyboard"
    new_device.metadata.serial = "NEW123"
    new_device.metadata.location = "New Location"
    new_device.metadata.version = "2.0.0"
    new_device.active_mode = 0
    new_device.modes = mock_openrgb_device.modes
    new_device.colors = [RGBColor(0, 255, 0)]
    new_device.set_color = MagicMock()
    new_device.set_mode = MagicMock()

    mock_openrgb_client.devices = [mock_openrgb_device, new_device]

    # Manually trigger coordinator refresh
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()

    # Check that second light entity was added
    state = hass.states.get("light.new_rgb_device")
    assert state


@pytest.mark.usefixtures("init_integration")
async def test_light_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
) -> None:
    """Test light becomes unavailable when device is unplugged."""
    state = hass.states.get("light.test_rgb_device")
    assert state
    assert state.state == STATE_ON

    # Simulate device disconnection
    mock_openrgb_client.devices = []

    # Manually trigger coordinator refresh
    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()

    state = hass.states.get("light.test_rgb_device")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_duplicate_device_names(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_openrgb_device: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that devices with duplicate names get numeric suffixes."""
    # Create two devices with the same name but different serials and device IDs
    device1 = MagicMock()
    device1.id = 3  # Should get suffix "1"
    device1.name = "ENE DRAM"
    device1.type = MagicMock()
    device1.type.name = "DRAM"
    device1.metadata = MagicMock()
    device1.metadata.vendor = "ENE"
    device1.metadata.description = "RAM Module"
    device1.metadata.serial = "SERIAL001"
    device1.metadata.location = "DIMM_A1"
    device1.metadata.version = "1.0"
    device1.active_mode = 0
    device1.modes = mock_openrgb_device.modes
    device1.colors = [RGBColor(255, 0, 0)]
    device1.set_color = MagicMock()
    device1.set_mode = MagicMock()

    device2 = MagicMock()
    device2.id = 4  # Should get suffix "2"
    device2.name = "ENE DRAM"
    device2.type = MagicMock()
    device2.type.name = "DRAM"
    device2.metadata = MagicMock()
    device2.metadata.vendor = "ENE"
    device2.metadata.description = "RAM Module"
    device2.metadata.serial = "SERIAL002"
    device2.metadata.location = "DIMM_A2"
    device2.metadata.version = "1.0"
    device2.active_mode = 0
    device2.modes = mock_openrgb_device.modes
    device2.colors = [RGBColor(0, 255, 0)]
    device2.set_color = MagicMock()
    device2.set_mode = MagicMock()

    mock_openrgb_client.devices = [device1, device2]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Get device keys (they will be sorted alphabetically)
    # The device key format is: entry_id||type||vendor||description||serial||location
    device1_key = (
        f"{mock_config_entry.entry_id}||DRAM||ENE||RAM Module||SERIAL001||DIMM_A1"
    )
    device2_key = (
        f"{mock_config_entry.entry_id}||DRAM||ENE||RAM Module||SERIAL002||DIMM_A2"
    )

    # Verify devices exist with correct names (suffix based on device.id, not keys)
    device1_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, device1_key)}
    )
    device2_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, device2_key)}
    )

    assert device1_entry
    assert device2_entry

    # device1 has lower device.id, so it gets suffix "1"
    # device2 has higher device.id, so it gets suffix "2"
    assert device1_entry.name == "ENE DRAM 1"
    assert device2_entry.name == "ENE DRAM 2"
