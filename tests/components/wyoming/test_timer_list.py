"""Test Wyoming timer list."""

from homeassistant.components.assist_satellite import DATA_COMPONENT
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_timer_list(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test the satellite has a timer list on its device."""
    timer_list_entity_id = satellite_device.get_timer_list_entity_id(hass)
    assert timer_list_entity_id == "timer_list.office_test_satellite_timers"

    state = hass.states.get(timer_list_entity_id)
    assert state is not None
    assert state.state == "0"
    assert state.attributes["friendly_name"] == "Test Satellite Timers"

    entity_entry = entity_registry.async_get(timer_list_entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{satellite_config_entry.entry_id}-timers"
    assert entity_entry.device_id == satellite_device.device_id

    satellites = list(hass.data[DATA_COMPONENT].entities)
    assert [satellite.timer_list_entity_id for satellite in satellites] == [
        timer_list_entity_id
    ]
