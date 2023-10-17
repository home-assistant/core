"""Tests for lawn_mower module."""
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

from aioautomower.session import AutomowerSession
import pytest

from homeassistant.components.husqvarna_automower import DOMAIN
from homeassistant.components.husqvarna_automower.lawn_mower import (
    AutomowerLawnMowerEntity,
)
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import AUTOMOWER_CONFIG_DATA, AUTOMOWER_SM_SESSION_DATA, MWR_ONE_ID
from .utils import make_mower_data

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

    deepcopy(AUTOMOWER_SM_SESSION_DATA)
    mower = make_mower_data()

    with patch(
        "aioautomower.AutomowerSession",
        return_value=AsyncMock(
            name="AutomowerMockSession",
            model=AutomowerSession,
            data=mower,
            register_data_callback=MagicMock(),
            unregister_data_callback=MagicMock(),
            connect=AsyncMock(),
            action=AsyncMock(),
        ),
    ), patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
    ) as mock_impl:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state == ConfigEntryState.LOADED
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        mock_impl.assert_called_once()

    return config_entry


@pytest.mark.asyncio
async def test_lawn_mower_state(hass: HomeAssistant) -> None:
    """Test lawn_mower state."""
    mower = make_mower_data()
    await setup_entity(hass)
    coordinator = hass.data[DOMAIN]["automower_test"]
    lawn_mower = AutomowerLawnMowerEntity(mower.data[0], coordinator)

    def set_state(state: str):
        """Set new state."""
        mower.data[0].attributes.mower.state = state

    def set_activity(activity: str):
        """Set new state."""
        mower.data[0].attributes.mower.activity = activity

    assert lawn_mower._attr_unique_id == f"{MWR_ONE_ID}_lawn_mower"
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

    mower = make_mower_data()
    await setup_entity(hass)
    coordinator = hass.data[DOMAIN]["automower_test"]
    lawn_mower = AutomowerLawnMowerEntity(mower.data[0], coordinator)
    assert lawn_mower._attr_unique_id == f"{MWR_ONE_ID}_lawn_mower"

    # Start
    # Success
    await lawn_mower.async_start_mowing()
    coordinator.session.resume_schedule.assert_awaited_once_with(MWR_ONE_ID)

    # Pause
    # Success
    await lawn_mower.async_pause()
    coordinator.session.pause_mowing.assert_awaited_once_with(MWR_ONE_ID)

    # Stop
    # Success
    await lawn_mower.async_dock()
    coordinator.session.park_until_next_schedule.assert_awaited_once_with(MWR_ONE_ID)
