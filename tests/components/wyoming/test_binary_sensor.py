"""Test Wyoming binary sensor devices."""
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import reload_satellite


async def test_assist_in_progress(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test assist in progress."""
    assist_in_progress_id = satellite_device.get_assist_in_progress_entity_id(hass)
    assert assist_in_progress_id

    state = hass.states.get(assist_in_progress_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite_device.is_active

    satellite_device.set_is_active(True)

    state = hass.states.get(assist_in_progress_id)
    assert state is not None
    assert state.state == STATE_ON
    assert satellite_device.is_active

    # test restore does *not* happen
    satellite_device = await reload_satellite(hass, satellite_config_entry.entry_id)

    state = hass.states.get(assist_in_progress_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite_device.is_active
