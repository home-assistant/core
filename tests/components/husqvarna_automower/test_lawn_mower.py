"""Tests for lawn_mower module."""
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower import AutomowerSession
from aiohttp import ClientResponseError
import pytest

from homeassistant.components.husqvarna_automower import DOMAIN
from homeassistant.components.husqvarna_automower.lawn_mower import (
    HusqvarnaAutomowerEntity,
)
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import (
    AUTOMOWER_CONFIG_DATA,
    AUTOMOWER_SM_SESSION_DATA,
    MWR_ONE_ID,
    MWR_ONE_IDX,
)

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def setup_entity(hass: HomeAssistant):
    """Set up entity and config entry."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=AUTOMOWER_CONFIG_DATA,
        entry_id="automower_test",
        title="Automower Test",
    )

    config_entry.add_to_hass(hass)

    session = deepcopy(AUTOMOWER_SM_SESSION_DATA)

    with patch(
        "aioautomower.AutomowerSession",
        return_value=AsyncMock(
            name="AutomowerMockSession",
            model=AutomowerSession,
            data=session,
            register_data_callback=MagicMock(),
            unregister_data_callback=MagicMock(),
            register_token_callback=MagicMock(),
            connect=AsyncMock(),
            action=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    return config_entry


@pytest.mark.asyncio
async def test_lawn_mower_state(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    await setup_entity(hass)
    coordinator = hass.data[DOMAIN]["automower_test"]
    lawn_mower = HusqvarnaAutomowerEntity(coordinator, MWR_ONE_IDX)

    def set_state(state: str):
        """Set new state."""
        coordinator.session.data["data"][MWR_ONE_IDX]["attributes"]["mower"][
            "state"
        ] = state

    def set_activity(activity: str):
        """Set new state."""
        coordinator.session.data["data"][MWR_ONE_IDX]["attributes"]["mower"][
            "activity"
        ] = activity

    assert lawn_mower._attr_unique_id == MWR_ONE_ID
    set_activity("")

    set_state("PAUSED")
    assert lawn_mower.state == LawnMowerActivity.PAUSED

    set_state("WAIT_UPDATING")
    assert lawn_mower.state == LawnMowerActivity.PAUSED

    set_state("WAIT_POWER_UP")
    assert lawn_mower.state == LawnMowerActivity.PAUSED

    set_state("")
    set_activity("MOWING")
    assert lawn_mower.state == LawnMowerActivity.MOWING

    set_activity("LEAVING")
    assert lawn_mower.state == LawnMowerActivity.MOWING

    set_activity("GOING_HOME")
    assert lawn_mower.state == LawnMowerActivity.MOWING

    set_activity("")
    set_state("RESTRICTED")
    assert lawn_mower.state == LawnMowerActivity.DOCKED

    set_state("")
    set_activity("PARKED_IN_CS")
    assert lawn_mower.state == LawnMowerActivity.DOCKED

    set_activity("CHARGING")
    assert lawn_mower.state == LawnMowerActivity.DOCKED

    set_activity("")
    set_state("FATAL_ERROR")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("ERROR")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("ERROR_AT_POWER_UP")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("NOT_APPLICABLE")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("UNKNOWN")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("STOPPED")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("OFF")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_state("")
    set_activity("STOPPED_IN_GARDEN")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_activity("UNKNOWN")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_activity("NOT_APPLICABLE")
    assert lawn_mower.state == LawnMowerActivity.ERROR

    set_activity("SOMETHING_NEW")
    assert lawn_mower.state == LawnMowerActivity.ERROR


@pytest.mark.asyncio
async def test_lawn_mower_commands(hass: HomeAssistant) -> None:
    """Test lawn_mower commands."""
    await setup_entity(hass)
    coordinator = hass.data[DOMAIN]["automower_test"]
    lawn_mower = HusqvarnaAutomowerEntity(coordinator, MWR_ONE_IDX)
    assert lawn_mower._attr_unique_id == MWR_ONE_ID

    # Start
    # Success
    await lawn_mower.async_start_mowing()
    coordinator.session.action.assert_awaited_once_with(
        MWR_ONE_ID, '{"data": {"type": "ResumeSchedule"}}', "actions"
    )

    # Raises ClientResponseError
    coordinator.session.action.reset_mock()
    coordinator.session.action.side_effect = ClientResponseError(
        MagicMock(), MagicMock()
    )
    await lawn_mower.async_start_mowing()

    # Pause
    # Success
    coordinator.session.action.reset_mock()
    await lawn_mower.async_pause()
    coordinator.session.action.assert_awaited_once_with(
        MWR_ONE_ID, '{"data": {"type": "Pause"}}', "actions"
    )

    # Raises ClientResponseError
    coordinator.session.action.reset_mock()
    coordinator.session.action.side_effect = ClientResponseError(
        MagicMock(), MagicMock()
    )
    await lawn_mower.async_pause()

    # Stop
    # Success
    coordinator.session.action.reset_mock()
    await lawn_mower.async_dock()
    coordinator.session.action.assert_awaited_once_with(
        MWR_ONE_ID, '{"data": {"type": "ParkUntilNextSchedule"}}', "actions"
    )

    # Raises ClientResponseError
    coordinator.session.action.reset_mock()
    coordinator.session.action.side_effect = ClientResponseError(
        MagicMock(), MagicMock()
    )
    await lawn_mower.async_dock()
