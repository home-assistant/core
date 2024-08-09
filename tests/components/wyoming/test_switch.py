"""Test Wyoming switch devices."""

from homeassistant.components.wyoming.satellite import WyomingSatellite
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import reload_satellite


async def test_muted(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite: WyomingSatellite,
) -> None:
    """Test satellite muted."""
    muted_id = satellite.device.get_muted_entity_id(hass)
    assert muted_id

    state = hass.states.get(muted_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite.device.is_muted

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": muted_id},
        blocking=True,
    )

    state = hass.states.get(muted_id)
    assert state is not None
    assert state.state == STATE_ON
    assert satellite.is_muted
    assert satellite.device.is_muted

    # test restore
    satellite.device = await reload_satellite(hass, satellite_config_entry.entry_id)

    state = hass.states.get(muted_id)
    assert state is not None
    assert state.state == STATE_ON
    assert satellite.is_muted
    assert satellite.device.is_muted

    # test mute from entity
    await satellite.async_set_mute(False)

    state = hass.states.get(muted_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite.is_muted
    assert not satellite.device.is_muted
