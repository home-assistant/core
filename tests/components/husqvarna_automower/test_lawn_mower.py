"""Tests for lawn_mower module."""

from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)


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

    for activity, state, expected_state in [
        ("UNKNOWN", "PAUSED", LawnMowerActivity.PAUSED),
        ("MOWING", "NOT_APPLICABLE", LawnMowerActivity.MOWING),
        ("NOT_APPLICABLE", "ERROR", LawnMowerActivity.ERROR),
    ]:
        values[TEST_MOWER_ID].mower.activity = activity
        values[TEST_MOWER_ID].mower.state = state
        mock_automower_client.get_status.return_value = values
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        state = hass.states.get("lawn_mower.test_mower_1")
        assert state.state == expected_state


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
    getattr(
        mock_automower_client.commands, aioautomower_command
    ).side_effect = ApiException("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Command couldn't be sent to the command queue: Test error",
    ):
        await hass.services.async_call(
            domain="lawn_mower",
            service=service,
            service_data={"entity_id": "lawn_mower.test_mower_1"},
            blocking=True,
        )
