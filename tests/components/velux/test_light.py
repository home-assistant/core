"""Test Velux light entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import update_callback_entity

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

# Apply setup_integration fixture to all tests in this module
pytestmark = pytest.mark.usefixtures("setup_integration")


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.LIGHT


@pytest.mark.parametrize(
    "mock_pyvlx", ["mock_light", "mock_onoff_light"], indirect=True
)
async def test_light_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the entity and validate registry metadata for light entities."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )


async def test_light_device_association(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_light: AsyncMock,
) -> None:
    """Test light device association."""

    test_entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    # Get entity + device entry
    entity_entry = entity_registry.async_get(test_entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None

    # Verify device has correct identifiers + name
    assert ("velux", mock_light.serial_number) in device_entry.identifiers
    assert device_entry.name == mock_light.name


# This test is not light specific, it just uses the light platform to test the base entity class.
async def test_entity_callbacks(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_light: AsyncMock,
) -> None:
    """Ensure the entity unregisters its device-updated callback when unloaded."""
    # Entity is created by setup_integration; callback should be registered
    test_entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"
    state = hass.states.get(test_entity_id)
    assert state is not None

    # Callback is registered exactly once with a callable
    assert mock_light.register_device_updated_cb.call_count == 1
    cb = mock_light.register_device_updated_cb.call_args[0][0]
    assert callable(cb)

    # Unload the config entry to trigger async_will_remove_from_hass
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Callback must be unregistered with the same callable
    assert mock_light.unregister_device_updated_cb.call_count == 1
    assert mock_light.unregister_device_updated_cb.call_args[0][0] is cb


# Test availability functionality by using the light platform
async def test_entity_availability(
    hass: HomeAssistant, mock_light: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that entity availability updates based on device connection status."""

    entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    # Initially connected
    mock_light.pyvlx.get_connected.return_value = True
    await update_callback_entity(hass, mock_light)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"

    # Simulate disconnection
    mock_light.pyvlx.get_connected.return_value = False
    await update_callback_entity(hass, mock_light)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"
    assert caplog.text.count(f"Entity {entity_id} is unavailable") == 1

    # Simulate disconnection, check we don't log again
    mock_light.pyvlx.get_connected.return_value = False
    await update_callback_entity(hass, mock_light)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unavailable"
    assert caplog.text.count(f"Entity {entity_id} is unavailable") == 1

    # Simulate reconnection
    mock_light.pyvlx.get_connected.return_value = True
    await update_callback_entity(hass, mock_light)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"
    assert caplog.text.count(f"Entity {entity_id} is back online") == 1

    # Simulate reconnection, check we don't log again
    mock_light.pyvlx.get_connected.return_value = True
    await update_callback_entity(hass, mock_light)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != "unavailable"
    assert caplog.text.count(f"Entity {entity_id} is back online") == 1


async def test_light_brightness_and_is_on(
    hass: HomeAssistant, mock_light: AsyncMock
) -> None:
    """Validate brightness mapping and on/off state from intensity."""

    entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    # Set initial intensity values
    mock_light.intensity.intensity_percent = 20  # 20% "intensity" -> 20% brightness
    mock_light.intensity.off = False
    mock_light.intensity.known = True

    # Trigger state write
    await update_callback_entity(hass, mock_light)

    state = hass.states.get(entity_id)
    assert state is not None
    # brightness = int(20 * 255 / 100) = int(51)
    assert state.attributes.get("brightness") == 51
    assert state.state == "on"

    # Mark as off
    mock_light.intensity.off = True
    await update_callback_entity(hass, mock_light)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_light_turn_on_with_brightness_uses_set_intensity(
    hass: HomeAssistant, mock_light: AsyncMock
) -> None:
    """Turning on with brightness calls set_intensity with percent."""

    entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    # Call turn_on with brightness=51 (20% when normalized)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id, ATTR_BRIGHTNESS: 51},
        blocking=True,
    )

    # set_intensity called once; turn_on should not be used in this path
    assert mock_light.set_intensity.await_count == 1
    assert mock_light.turn_on.await_count == 0

    # Inspect the intensity argument (first positional)
    args, kwargs = mock_light.set_intensity.await_args
    intensity_obj = args[0]
    # brightness 51 -> 20% normalized -> intensity_percent = 20
    assert intensity_obj.intensity_percent == 20
    assert kwargs.get("wait_for_completion") is True


async def test_light_turn_on_without_brightness_calls_turn_on(
    hass: HomeAssistant, mock_light: AsyncMock
) -> None:
    """Turning on without brightness uses device.turn_on."""

    entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_light.turn_on.assert_awaited_once_with(wait_for_completion=True)
    assert mock_light.set_intensity.await_count == 0


async def test_light_turn_off_calls_turn_off(
    hass: HomeAssistant, mock_light: AsyncMock
) -> None:
    """Turning off calls device.turn_off with wait_for_completion."""

    entity_id = f"light.{mock_light.name.lower().replace(' ', '_')}"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )

    mock_light.turn_off.assert_awaited_once_with(wait_for_completion=True)
