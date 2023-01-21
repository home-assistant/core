"""Test for Powerwall off-grid switch."""

from unittest.mock import Mock, patch

from tesla_powerwall import GridStatus

from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_IP_ADDRESS, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as ent_reg

from .mocks import _mock_powerwall_with_fixtures

from tests.common import MockConfigEntry

ENTITY_ID = "switch.take_powerwall_off_grid"


async def test_entity_registry(hass):
    """Test powerwall off-grid switch device."""

    await _mock_hass_powerwall_with_grid_status(hass, GridStatus.CONNECTED)
    entity_registry = ent_reg.async_get(hass)

    assert ENTITY_ID in entity_registry.entities


async def test_initial_gridstatus(hass):
    """Test initial grid status without off grid switch selected."""

    await _mock_hass_powerwall_with_grid_status(hass, GridStatus.CONNECTED)

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_gridstatus_off(hass):
    """Test state once offgrid switch has been turned on."""

    await _mock_hass_powerwall_with_grid_status(hass, GridStatus.ISLANDED)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_gridstatus_on(hass):
    """Test state once offgrid switch has been turned off."""

    await _mock_hass_powerwall_with_grid_status(hass, GridStatus.CONNECTED)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_turn_on_without_entity_id(hass):
    """Test switch turn on all switches."""

    await _mock_hass_powerwall_with_grid_status(hass, GridStatus.ISLANDED)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_turn_off_without_entity_id(hass):
    """Test switch turn off all switches."""

    await _mock_hass_powerwall_with_grid_status(hass, GridStatus.CONNECTED)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def _mock_hass_powerwall_with_grid_status(hass, expected_grid_status: GridStatus):
    """Reusable mock setup which changes only the expected return value for Grid Status."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall.get_grid_status = Mock(return_value=expected_grid_status)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
