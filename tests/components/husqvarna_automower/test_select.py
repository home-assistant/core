"""Tests for select platform."""

from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.model import HeadlightModes
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)


async def test_select_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test states of headlight mode select."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("select.test_mower_1_headlight_mode")
    assert state is not None
    assert state.state == "evening_only"

    for state, expected_state in [
        (
            HeadlightModes.ALWAYS_OFF,
            "always_off",
        ),
        (HeadlightModes.ALWAYS_ON, "always_on"),
        (HeadlightModes.EVENING_AND_NIGHT, "evening_and_night"),
    ]:
        values[TEST_MOWER_ID].headlight.mode = state
        mock_automower_client.get_status.return_value = values
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        state = hass.states.get("select.test_mower_1_headlight_mode")
        assert state.state == expected_state


@pytest.mark.parametrize(
    ("service"),
    [
        ("always_on"),
        ("always_off"),
        ("evening_only"),
        ("evening_and_night"),
    ],
)
async def test_select_commands(
    hass: HomeAssistant,
    service: str,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select commands for headlight mode."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        domain="select",
        service="select_option",
        service_data={
            "entity_id": "select.test_mower_1_headlight_mode",
            "option": service,
        },
        blocking=True,
    )
    mocked_method = mock_automower_client.set_headlight_mode
    assert len(mocked_method.mock_calls) == 1

    mocked_method.side_effect = ApiException("Test error")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            domain="select",
            service="select_option",
            service_data={
                "entity_id": "select.test_mower_1_headlight_mode",
                "option": service,
            },
            blocking=True,
        )
    assert (
        str(exc_info.value)
        == "Command couldn't be sent to the command queue: Test error"
    )
    assert len(mocked_method.mock_calls) == 2
