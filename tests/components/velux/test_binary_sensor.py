"""Tests for the Velux binary sensor platform."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.velux import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import update_polled_entities

from tests.common import MockConfigEntry


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.BINARY_SENSOR


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rain_sensor_state(
    hass: HomeAssistant,
    mock_window: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the rain sensor."""

    test_entity_id = "binary_sensor.test_window_rain_sensor"

    # simulate no rain detected
    await update_polled_entities(hass, freezer)
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # simulate rain detected (Velux GPU reports 100)
    mock_window.get_limitation.return_value.min_value = 100
    await update_polled_entities(hass, freezer)
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # simulate rain detected (other Velux models report 93)
    mock_window.get_limitation.return_value.min_value = 93
    await update_polled_entities(hass, freezer)
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_ON

    # simulate no rain detected again
    mock_window.get_limitation.return_value.min_value = 95
    await update_polled_entities(hass, freezer)
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rain_sensor_device_association(
    hass: HomeAssistant,
    mock_window: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test the rain sensor is properly associated with its device."""

    test_entity_id = "binary_sensor.test_window_rain_sensor"

    # Verify entity exists
    state = hass.states.get(test_entity_id)
    assert state is not None

    # Get entity entry
    entity_entry = entity_registry.async_get(test_entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None

    # Get device entry
    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None

    # Verify device has correct identifiers
    assert ("velux", mock_window.serial_number) in device_entry.identifiers
    assert device_entry.name == mock_window.name

    # Verify via_device is gateway
    assert device_entry.via_device_id is not None
    via_device_entry = device_registry.async_get(device_entry.via_device_id)
    assert via_device_entry is not None
    assert via_device_entry.identifiers == {
        (DOMAIN, f"gateway_{mock_config_entry.entry_id}")
    }
