"""Tests for the Rituals Perfume Genie sensor platform."""

from homeassistant.components.rituals_perfume_genie.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    init_integration,
    mock_config_entry,
    mock_diffuser_v1_battery_cartridge,
)


async def test_sensors_diffuser_v1_battery_cartridge(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the creation and values of the Rituals Perfume Genie sensors."""
    config_entry = mock_config_entry(unique_id="id_123_sensor_test_diffuser_v1")
    diffuser = mock_diffuser_v1_battery_cartridge()
    await init_integration(hass, config_entry, [diffuser])
    hublot = diffuser.hublot

    state = hass.states.get("sensor.genie_perfume")
    assert state
    assert state.state == diffuser.perfume

    entry = entity_registry.async_get("sensor.genie_perfume")
    assert entry
    assert entry.unique_id == f"{hublot}-perfume"

    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == diffuser.fill

    entry = entity_registry.async_get("sensor.genie_fill")
    assert entry
    assert entry.unique_id == f"{hublot}-fill"

    state = hass.states.get("sensor.genie_battery")
    assert state
    assert state.state == str(diffuser.battery_percentage)
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = entity_registry.async_get("sensor.genie_battery")
    assert entry
    assert entry.unique_id == f"{hublot}-battery_percentage"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get("sensor.genie_wi_fi_signal")
    assert state
    assert state.state == str(diffuser.wifi_percentage)
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    entry = entity_registry.async_get("sensor.genie_wi_fi_signal")
    assert entry
    assert entry.unique_id == f"{hublot}-wifi_percentage"
    assert entry.entity_category == EntityCategory.DIAGNOSTIC
