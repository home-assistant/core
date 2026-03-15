"""Tests for the Litter-Robot coordinator."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pylitterbot.exceptions import LitterRobotException, LitterRobotLoginException

from homeassistant.components.litterrobot.const import DOMAIN
from homeassistant.components.litterrobot.coordinator import UPDATE_INTERVAL
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import VACUUM_ENTITY_ID
from .conftest import setup_integration

from tests.common import async_fire_time_changed


async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_account: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when coordinator update fails."""
    await setup_integration(hass, mock_account, VACUUM_DOMAIN)

    assert (state := hass.states.get(VACUUM_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE

    # Simulate an API error during update
    mock_account.refresh_robots.side_effect = LitterRobotException("Unable to connect")
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(VACUUM_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    # Recover
    mock_account.refresh_robots.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(VACUUM_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE


async def test_coordinator_update_auth_error(
    hass: HomeAssistant,
    mock_account: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test reauthentication flow is triggered on login error during update."""
    entry = await setup_integration(hass, mock_account, VACUUM_DOMAIN)

    assert (state := hass.states.get(VACUUM_ENTITY_ID))
    assert state.state != STATE_UNAVAILABLE

    # Simulate an authentication error during update
    mock_account.refresh_robots.side_effect = LitterRobotLoginException(
        "Invalid credentials"
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(VACUUM_ENTITY_ID))
    assert state.state == STATE_UNAVAILABLE

    # Ensure a reauthentication flow was triggered
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
