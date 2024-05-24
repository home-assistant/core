"""Tests for lawn_mower module."""

from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.components.husqvarna_automower.lawn_mower import EXCEPTION_TEXT
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
    ("domain", "aioautomower_command", "service", "service_data"),
    [
        ("lawn_mower", "resume_schedule", "start_mowing", None),
        ("lawn_mower", "pause_mowing", "pause", None),
        ("lawn_mower", "park_until_next_schedule", "dock", None),
        (DOMAIN, "start_for", "start_for", {"duration": 123}),
        (DOMAIN, "park_for", "park_for", {"duration": "321"}),
    ],
)
async def test_lawn_mower_commands(
    hass: HomeAssistant,
    domain: str,
    aioautomower_command: str,
    service: str,
    service_data: dict[str, int] | None,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)
    mocked_method = getattr(mock_automower_client.commands, aioautomower_command)
    await hass.services.async_call(
        domain=domain,
        service=service,
        target={"entity_id": "lawn_mower.test_mower_1"},
        service_data=service_data,
        blocking=True,
    )
    assert len(mocked_method.mock_calls) == 1

    getattr(
        mock_automower_client.commands, aioautomower_command
    ).side_effect = ApiException("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Command couldn't be sent to the command queue: Test error",
    ):
        await hass.services.async_call(
            domain=domain,
            service=service,
            target={"entity_id": "lawn_mower.test_mower_1"},
            service_data=service_data,
            blocking=True,
        )
