"""Tests for switch platform."""
from datetime import timedelta
from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerStates, RestrictedReasons
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)


async def test_switch_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch state."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)

    for state, restricted_reson, expected_state in [
        (MowerStates.RESTRICTED, RestrictedReasons.NOT_APPLICABLE, "on"),
        (MowerStates.IN_OPERATION, RestrictedReasons.NONE, "off"),
    ]:
        values[TEST_MOWER_ID].mower.state = state
        values[TEST_MOWER_ID].planner.restricted_reason = restricted_reson
        mock_automower_client.get_status.return_value = values
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        state = hass.states.get("switch.test_mower_1_park_until_further_notice")
        assert state.state == expected_state


@pytest.mark.parametrize(
    ("service", "aioautomower_command"),
    [
        ("turn_on", "park_until_further_notice"),
        ("turn_off", "resume_schedule"),
        ("toggle", "park_until_further_notice"),
    ],
)
async def test_lawn_mower_commands(
    hass: HomeAssistant,
    aioautomower_command: str,
    service: str,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test switch commands."""
    await setup_integration(hass, mock_config_entry)

    getattr(mock_automower_client, aioautomower_command).side_effect = ApiException(
        "Test error"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            domain="switch",
            service=service,
            service_data={"entity_id": "switch.test_mower_1_park_until_further_notice"},
            blocking=True,
        )
    assert (
        str(exc_info.value)
        == "Command couldn't be sent to the command queue: Test error"
    )
