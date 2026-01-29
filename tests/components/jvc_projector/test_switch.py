"""Tests for JVC Projector switch platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from jvcprojector import command as cmd

from homeassistant.components.jvc_projector.coordinator import INTERVAL_FAST
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed

ESHIFT_ENTITY_ID = "switch.jvc_projector_e_shift"
LOW_LATENCY_ENTITY_ID = "switch.jvc_projector_low_latency_mode"


async def test_switch_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_device: MagicMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test switch entities."""
    entity_registry.async_update_entity(ESHIFT_ENTITY_ID, disabled_by=None)
    await hass.config_entries.async_reload(mock_integration.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass, utcnow() + timedelta(seconds=INTERVAL_FAST.seconds + 1)
    )
    await hass.async_block_till_done()

    eshift = hass.states.get(ESHIFT_ENTITY_ID)
    assert eshift
    assert eshift.attributes.get(ATTR_FRIENDLY_NAME) == "JVC Projector E-Shift"
    assert eshift.state == "on"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ESHIFT_ENTITY_ID},
        blocking=True,
    )

    mock_device.set.assert_any_call(cmd.EShift, "off")

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ESHIFT_ENTITY_ID},
        blocking=True,
    )

    mock_device.set.assert_any_call(cmd.EShift, "on")
