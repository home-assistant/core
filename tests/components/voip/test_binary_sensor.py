"""Test VoIP binary sensor devices."""
from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_allow_call(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    voip_device: VoIPDevice,
) -> None:
    """Test allow call."""
    state = hass.states.get("binary_sensor.192_168_1_210_call_active")
    assert state is not None
    assert state.state == "off"

    voip_device.set_is_active(True)

    state = hass.states.get("binary_sensor.192_168_1_210_call_active")
    assert state.state == "on"

    voip_device.set_is_active(False)

    state = hass.states.get("binary_sensor.192_168_1_210_call_active")
    assert state.state == "off"
