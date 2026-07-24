"""Tests for the Hinen sensor platform."""

from homeassistant.components.hinen_power.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ComponentSetup


async def test_sensors_added_correctly(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test sensors are added correctly."""
    await setup_integration()
    await hass.async_block_till_done()
    entity_registry = er.async_get(hass)

    # Test status sensor
    status_entity = entity_registry.async_get("sensor.test_hinen_device_status")
    assert status_entity is not None
    assert status_entity.unique_id == "device_12345_device_12345_status"


async def test_sensor_states(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test sensor states are correctly reported."""
    await setup_integration()
    await hass.async_block_till_done()

    # Test status sensor state
    status_state = hass.states.get("sensor.test_hinen_device_status")
    assert status_state is not None
    assert status_state.state == "normal"


async def test_sensor_native_value_when_device_missing(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test sensor native_value returns None when coordinator device data is missing."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await setup_integration()
    await hass.async_block_till_done()

    entry.runtime_data.coordinator.data.pop("device_12345", None)

    entity = er.async_get(hass).async_get("sensor.test_hinen_device_status")
    assert entity is not None

    sensor = hass.data.get("entity_components", {}).get("sensor")
    assert sensor is not None
    hinen_sensor = sensor.get_entity(entity.entity_id)
    assert hinen_sensor is not None
    assert hinen_sensor.native_value is None
