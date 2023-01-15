"""Tests for the comfoconnect fan platform."""

from homeassistant.const import STATE_OFF

from .const import COMPONENT, CONF_DATA as VALID_CONFIG

from tests.common import MockConfigEntry


async def test_fan(hass, mock_bridge_discover, mock_comfoconnect_command):
    """Test the fan."""
    config_entry = MockConfigEntry(
        domain=COMPONENT,
        data=VALID_CONFIG,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "fan.comfoairq"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.name == "ComfoAirQ"
    assert state.attributes.get("preset_modes") == ["auto"]
    assert state.attributes.get("icon") == "mdi:air-conditioner"
