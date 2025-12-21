"""Test VoIP switch devices."""

from homeassistant.components.voip.devices import VoIPDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def test_allow_call(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    voip_device: VoIPDevice,
) -> None:
    """Test allow call."""
    assert not voip_device.async_allow_call(hass)

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state is not None
    assert state.state == "off"

    await hass.config_entries.async_reload(config_entry.entry_id)

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state.state == "off"

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.192_168_1_210_allow_calls"},
        blocking=True,
    )

    assert voip_device.async_allow_call(hass)

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state.state == "on"

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state.state == "on"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.192_168_1_210_allow_calls"},
        blocking=True,
    )

    assert not voip_device.async_allow_call(hass)

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state.state == "off"
