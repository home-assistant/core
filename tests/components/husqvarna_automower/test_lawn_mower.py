"""Tests for lawn_mower module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
import pytest
from voluptuous.error import MultipleInvalid

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

    for activity, state, expected_state in (
        ("UNKNOWN", "PAUSED", LawnMowerActivity.PAUSED),
        ("MOWING", "NOT_APPLICABLE", LawnMowerActivity.MOWING),
        ("NOT_APPLICABLE", "ERROR", LawnMowerActivity.ERROR),
    ):
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
    await hass.services.async_call(
        domain="lawn_mower",
        service=service,
        service_data={"entity_id": "lawn_mower.test_mower_1"},
        blocking=True,
    )
    mocked_method = getattr(mock_automower_client.commands, aioautomower_command)
    mocked_method.assert_called_once_with(TEST_MOWER_ID)

    getattr(
        mock_automower_client.commands, aioautomower_command
    ).side_effect = ApiException("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Failed to send command: Test error",
    ):
        await hass.services.async_call(
            domain="lawn_mower",
            service=service,
            target={"entity_id": "lawn_mower.test_mower_1"},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("aioautomower_command", "extra_data", "service", "service_data"),
    [
        (
            "start_for",
            timedelta(hours=3),
            "override_schedule",
            {
                "duration": {"days": 0, "hours": 3, "minutes": 0},
                "override_mode": "mow",
            },
        ),
        (
            "park_for",
            timedelta(days=1, hours=12, minutes=30),
            "override_schedule",
            {
                "duration": {"days": 1, "hours": 12, "minutes": 30},
                "override_mode": "park",
            },
        ),
    ],
)
async def test_lawn_mower_service_commands(
    hass: HomeAssistant,
    aioautomower_command: str,
    extra_data: int | None,
    service: str,
    service_data: dict[str, int] | None,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)
    mocked_method = AsyncMock()
    setattr(mock_automower_client.commands, aioautomower_command, mocked_method)
    await hass.services.async_call(
        domain=DOMAIN,
        service=service,
        target={"entity_id": "lawn_mower.test_mower_1"},
        service_data=service_data,
        blocking=True,
    )
    mocked_method.assert_called_once_with(TEST_MOWER_ID, extra_data)

    getattr(
        mock_automower_client.commands, aioautomower_command
    ).side_effect = ApiException("Test error")
    with pytest.raises(
        HomeAssistantError,
        match="Failed to send command: Test error",
    ):
        await hass.services.async_call(
            domain=DOMAIN,
            service=service,
            target={"entity_id": "lawn_mower.test_mower_1"},
            service_data=service_data,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            "override_schedule",
            {
                "duration": {"days": 1, "hours": 12, "minutes": 30},
                "override_mode": "fly_to_moon",
            },
        ),
    ],
)
async def test_lawn_mower_wrong_service_commands(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, int] | None,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(MultipleInvalid):
        await hass.services.async_call(
            domain=DOMAIN,
            service=service,
            target={"entity_id": "lawn_mower.test_mower_1"},
            service_data=service_data,
            blocking=True,
        )
