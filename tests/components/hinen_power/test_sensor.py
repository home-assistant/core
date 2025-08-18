"""Tests for the Hinen sensor platform."""

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
    assert (
        status_entity.unique_id
        == f"{status_entity.config_entry_id}_device_12345_status"
    )


async def test_sensor_states(
    hass: HomeAssistant, setup_integration: ComponentSetup
) -> None:
    """Test sensor states are correctly reported."""
    await setup_integration()
    await hass.async_block_till_done()

    # Test status sensor state
    status_state = hass.states.get("sensor.test_hinen_device_status")
    assert status_state is not None
    assert status_state.state == "NORMAL"
