"""Tests for lwan_mower module."""
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
    ) as automower_session_mock:
        (
            MagicMock(name="MockCoordinator", session=automower_session_mock()),
            patch(
                "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
            ),
        )

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    return config_entry


@pytest.mark.asyncio
async def test_vacuum_state(hass: HomeAssistant) -> None:
    """Test vacuum state."""
    await setup_entity(hass)
    coordinator = hass.data[DOMAIN]["automower_test"]
    vacuum = HusqvarnaAutomowerEntity(coordinator, MWR_ONE_IDX)

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

    assert vacuum._attr_unique_id == MWR_ONE_ID
    set_activity("")

    set_state("PAUSED")
    assert vacuum.state == LawnMowerActivity.PAUSED

    set_state("WAIT_UPDATING")
    assert vacuum.state == LawnMowerActivity.PAUSED

    set_state("WAIT_POWER_UP")
    assert vacuum.state == LawnMowerActivity.PAUSED

    set_state("")
    set_activity("MOWING")
    assert vacuum.state == LawnMowerActivity.MOWING

    set_activity("LEAVING")
    assert vacuum.state == LawnMowerActivity.MOWING

    set_activity("GOING_HOME")
    assert vacuum.state == LawnMowerActivity.MOWING

    set_activity("")
    set_state("RESTRICTED")
    assert vacuum.state == LawnMowerActivity.DOCKED

    set_state("")
    set_activity("PARKED_IN_CS")
    assert vacuum.state == LawnMowerActivity.DOCKED

    set_activity("CHARGING")
    assert vacuum.state == LawnMowerActivity.DOCKED

    set_activity("")
    set_state("FATAL_ERROR")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("ERROR")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("ERROR_AT_POWER_UP")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("NOT_APPLICABLE")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("UNKNOWN")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("STOPPED")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("OFF")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_state("")
    set_activity("STOPPED_IN_GARDEN")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_activity("UNKNOWN")
    assert vacuum.state == LawnMowerActivity.ERROR

    set_activity("NOT_APPLICABLE")
    assert vacuum.state == LawnMowerActivity.ERROR


@pytest.mark.asyncio
async def test_vacuum_commands(hass: HomeAssistant) -> None:
    """Test vacuum commands."""
    await setup_entity(hass)
    coordinator = hass.data[DOMAIN]["automower_test"]
    vacuum = HusqvarnaAutomowerEntity(coordinator, MWR_ONE_IDX)
    assert vacuum._attr_unique_id == MWR_ONE_ID

    # Start
    # Success
    await vacuum.async_start_mowing()
    coordinator.session.action.assert_awaited_once_with(
        MWR_ONE_ID, '{"data": {"type": "ResumeSchedule"}}', "actions"
    )

    # Raises ClientResponseError
    coordinator.session.action.reset_mock()
    coordinator.session.action.side_effect = ClientResponseError(
        MagicMock(), MagicMock()
    )
    await vacuum.async_start_mowing()

    # Pause
    # Success
    coordinator.session.action.reset_mock()
    await vacuum.async_pause()
    coordinator.session.action.assert_awaited_once_with(
        MWR_ONE_ID, '{"data": {"type": "Pause"}}', "actions"
    )

    # Raises ClientResponseError
    coordinator.session.action.reset_mock()
    coordinator.session.action.side_effect = ClientResponseError(
        MagicMock(), MagicMock()
    )
    await vacuum.async_pause()

    # Stop
    # Success
    coordinator.session.action.reset_mock()
    await vacuum.async_dock()
    coordinator.session.action.assert_awaited_once_with(
        MWR_ONE_ID, '{"data": {"type": "ParkUntilNextSchedule"}}', "actions"
    )

    # Raises ClientResponseError
    coordinator.session.action.reset_mock()
    coordinator.session.action.side_effect = ClientResponseError(
        MagicMock(), MagicMock()
    )
    await vacuum.async_dock()
