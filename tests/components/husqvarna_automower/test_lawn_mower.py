"""Tests for lawn_mower module."""
import logging
from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import ApiException
from aioautomower.utils import mower_list_to_dictionary_dataclass
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration

from tests.common import MockConfigEntry, load_json_value_fixture

_LOGGER = logging.getLogger(__name__)

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


@pytest.mark.parametrize(
    ("activity", "state", "target_state"),
    [
        ("PARKED_IN_CS", "RESTRICTED", LawnMowerActivity.DOCKED),
        ("UNKNOWN", "PAUSED", LawnMowerActivity.PAUSED),
        ("MOWING", "NOT_APPLICABLE", LawnMowerActivity.MOWING),
        ("NOT_APPLICABLE", "ERROR", LawnMowerActivity.ERROR),
    ],
)
async def test_lawn_mower_states(
    hass: HomeAssistant, setup_entity, target_state
) -> None:
    """Test lawn_mower state."""
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state is not None
    assert state.state == target_state


@pytest.mark.parametrize(
    ("aioautomower_command", "service"),
    [
        ("resume_schedule", "start_mowing"),
        ("pause_mowing", "pause"),
        ("park_until_next_schedule", "dock"),
    ],
)
async def test_lawn_mower_commands(
    hass: HomeAssistant, setup_entity, aioautomower_command, service
) -> None:
    """Test lawn_mower commands."""

    with pytest.raises(HomeAssistantError) as exc_info, patch(
        f"aioautomower.session.AutomowerSession.{aioautomower_command}",
        side_effect=ApiException("Test error"),
    ):
        await hass.services.async_call(
            domain="lawn_mower",
            service=service,
            service_data={"entity_id": "lawn_mower.test_mower_1"},
            blocking=True,
        )
    assert (
        str(exc_info.value) == "Command couldn't be sent to the command que: Test error"
    )


async def test_lawn_mower_states2(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower state."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    values[TEST_MOWER_ID].mower.activity = "UNKNOWN"
    values[TEST_MOWER_ID].mower.state = "PAUSED"
    mock_automower_client.get_status = values
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state is not None
    assert state.state == LawnMowerActivity.PAUSED
