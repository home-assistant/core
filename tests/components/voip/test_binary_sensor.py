"""Test VoIP binary sensor devices."""
from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_call_in_progress(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    voip_device: VoIPDevice,
) -> None:
    """Test call in progress."""
    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state is not None
    assert state.state == "off"

    voip_device.set_is_active(True)

    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state.state == "on"

    voip_device.set_is_active(False)

    state = hass.states.get("binary_sensor.192_168_1_210_call_in_progress")
    assert state.state == "off"
