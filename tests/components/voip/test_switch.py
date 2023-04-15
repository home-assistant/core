"""Test VoIP switch devices."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


async def test_allow_call(
    hass: HomeAssistant, config_entry, voip_devices, call_info
) -> None:
    """Test allow call."""
    assert not voip_devices.async_allow_call(call_info)
    await hass.async_block_till_done()

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

    assert voip_devices.async_allow_call(call_info)

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state.state == "on"

    await hass.config_entries.async_reload(config_entry.entry_id)

    state = hass.states.get("switch.192_168_1_210_allow_calls")
    assert state is not None
    assert state.state == "on"
