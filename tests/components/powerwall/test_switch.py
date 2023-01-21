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
    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = ent_reg.async_get(hass)

    assert ENTITY_ID in entity_registry.entities


async def test_initial_gridstatus(hass):
    """Test initial grid status without off grid switch selected."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_gridstatus_off(hass):
    """Test state once offgrid switch has been turned on."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall.get_grid_status = Mock(return_value=GridStatus.ISLANDED)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

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

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall.get_grid_status = Mock(return_value=GridStatus.CONNECTED)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

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

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall.get_grid_status = Mock(return_value=GridStatus.ISLANDED)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_ON


async def test_turn_off_without_entity_id(hass):
    """Test switch turn off all switches."""

    mock_powerwall = await _mock_powerwall_with_fixtures(hass)
    mock_powerwall.get_grid_status = Mock(return_value=GridStatus.CONNECTED)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.2.3.4"})
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.powerwall.Powerwall", return_value=mock_powerwall
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "all"}, blocking=True
    )

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
