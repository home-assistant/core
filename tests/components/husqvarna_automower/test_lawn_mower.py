"""Tests for lawn_mower module."""
from datetime import timedelta
import logging
from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)

_LOGGER = logging.getLogger(__name__)

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


async def test_lawn_mower_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lawn_mower state."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state is not None
    assert state.state == LawnMowerActivity.DOCKED

    values[TEST_MOWER_ID].mower.activity = "UNKNOWN"
    values[TEST_MOWER_ID].mower.state = "PAUSED"
    mock_automower_client.get_status.return_value = values = values
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state.state == LawnMowerActivity.PAUSED

    values[TEST_MOWER_ID].mower.activity = "MOWING"
    values[TEST_MOWER_ID].mower.state = "NOT_APPLICABLE"
    mock_automower_client.get_status.return_value = values = values
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state.state == LawnMowerActivity.MOWING

    values[TEST_MOWER_ID].mower.activity = "NOT_APPLICABLE"
    values[TEST_MOWER_ID].mower.state = "ERROR"
    mock_automower_client.get_status.return_value = values = values
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state.state == LawnMowerActivity.ERROR


@pytest.mark.parametrize(
    ("aioautomower_command", "service"),
    [
        ("resume_schedule", "start_mowing"),
        ("pause_mowing", "pause"),
        ("park_until_next_schedule", "dock"),
    ],
)
async def test_lawn_mower_commands(
    hass: HomeAssistant,
    aioautomower_command: str,
    service: str,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_automower_client, aioautomower_command).side_effect = ApiException(
        "Test error"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            domain="lawn_mower",
            service=service,
            service_data={"entity_id": "lawn_mower.test_mower_1"},
            blocking=True,
        )
    assert (
        str(exc_info.value) == "Command couldn't be sent to the command que: Test error"
    )
