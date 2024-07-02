"""Switch tests for the D-Link Smart Plug integration."""

from unittest.mock import patch

from homeassistant.components.dlink.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from .conftest import CONF_DATA

from tests.common import AsyncMock, MockConfigEntry


async def test_switch_state(hass: HomeAssistant, mocked_plug: AsyncMock) -> None:
    """Test we get the switch status."""
    with patch(
        "homeassistant.components.dlink.SmartPlug",
        return_value=mocked_plug,
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "switch.mock_title"
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes["total_consumption"] == 1040.0
    assert state.attributes["temperature"] == 33
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [entity_id]},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_switch_no_value(
    hass: HomeAssistant, mocked_plug_legacy: AsyncMock
) -> None:
    """Test we handle 'N/A' being passed by the pypi package."""
    with patch(
        "homeassistant.components.dlink.SmartPlug",
        return_value=mocked_plug_legacy,
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("switch.mock_title")
    assert state.state == STATE_OFF
    assert state.attributes["total_consumption"] is None
    assert state.attributes["temperature"] is None
