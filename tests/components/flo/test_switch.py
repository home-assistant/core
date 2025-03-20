"""Tests for the switch domain for Flo by Moen."""

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_valve_switches(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test Flo by Moen valve switches."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "switch.smart_water_shutoff_shutoff_valve"
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_ON
