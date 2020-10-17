"""Tests for Adaptive Lighting switches."""
from homeassistant.components import adaptive_lighting
from homeassistant.components.adaptive_lighting.const import (
    ATTR_TURN_ON_OFF_LISTENER,
    DEFAULT_NAME,
    DOMAIN,
    UNDO_UPDATE_LISTENER,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry


async def test_adaptive_lighting_switches(hass):
    """Test switches created for adaptive_lighting integration."""
    entry = MockConfigEntry(
        domain=adaptive_lighting.DOMAIN, data={CONF_NAME: DEFAULT_NAME}
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    assert hass.states.async_entity_ids(SWITCH_DOMAIN) == [
        f"{SWITCH_DOMAIN}.{DOMAIN}_{DEFAULT_NAME}",
        f"{SWITCH_DOMAIN}.{DOMAIN}_sleep_mode_{DEFAULT_NAME}",
    ]
    assert ATTR_TURN_ON_OFF_LISTENER in hass.data[DOMAIN]
    assert entry.entry_id in hass.data[DOMAIN]
    assert len(hass.data[DOMAIN].keys()) == 2

    data = hass.data[DOMAIN][entry.entry_id]
    assert "sleep_mode_switch" in data
    assert SWITCH_DOMAIN in data
    assert UNDO_UPDATE_LISTENER in data
    assert len(data.keys()) == 3
