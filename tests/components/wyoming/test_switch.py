"""Test Wyoming switch devices."""
from homeassistant.components.wyoming.devices import SatelliteDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


async def test_satellite_enabled(
    hass: HomeAssistant,
    satellite_config_entry: ConfigEntry,
    satellite_device: SatelliteDevice,
) -> None:
    """Test satellite enabled."""
    satellite_enabled_id = satellite_device.get_satellite_enabled_entity_id(hass)
    assert satellite_enabled_id

    state = hass.states.get(satellite_enabled_id)
    assert state is not None
    assert state.state == STATE_ON
    assert satellite_device.is_enabled

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": satellite_enabled_id},
        blocking=True,
    )

    state = hass.states.get(satellite_enabled_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert not satellite_device.is_enabled
