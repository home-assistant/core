"""Tests for lawn_mower module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiError
from aioautomower.model import MowerActivities, MowerAttributes, MowerStates
from freezegun.api import FrozenDateTimeFactory
import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.components.lawn_mower import LawnMowerActivity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("activity", "mower_state", "expected_state"),
    [
        (MowerActivities.UNKNOWN, MowerStates.PAUSED, LawnMowerActivity.PAUSED),
        (MowerActivities.MOWING, MowerStates.IN_OPERATION, LawnMowerActivity.MOWING),
        (MowerActivities.NOT_APPLICABLE, MowerStates.ERROR, LawnMowerActivity.ERROR),
        (
            MowerActivities.GOING_HOME,
            MowerStates.IN_OPERATION,
            LawnMowerActivity.RETURNING,
        ),
        (
            MowerActivities.NOT_APPLICABLE,
            MowerStates.IN_OPERATION,
            LawnMowerActivity.MOWING,
        ),
        (
            MowerActivities.PARKED_CS,
            MowerStates.IN_OPERATION,
            LawnMowerActivity.DOCKED
        ),
    ],
)
async def test_lawn_mower_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    values: dict[str, MowerAttributes],
    activity: MowerActivities,
    mower_state: MowerStates,
    expected_state: LawnMowerActivity,
) -> None:
    """Test lawn_mower state."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("lawn_mower.test_mower_1")
    assert state is not None
    assert state.state == LawnMowerActivity.DOCKED
    values[TEST_MOWER_ID].mower.activity = activity
    values[TEST_MOWER_ID].mower.state = mower_state
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

    mocked_method.side_effect = ApiError("Test error")
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
    extra_data: timedelta,
    service: str,
    service_data: dict[str, int] | None,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)
    mocked_method = getattr(mock_automower_client.commands, aioautomower_command)
    await hass.services.async_call(
        domain=DOMAIN,
        service=service,
        target={"entity_id": "lawn_mower.test_mower_1"},
        service_data=service_data,
        blocking=True,
    )
    mocked_method.assert_called_once_with(TEST_MOWER_ID, extra_data)

    mocked_method.side_effect = ApiError("Test error")
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
    ("aioautomower_command", "extra_data1", "extra_data2", "service", "service_data"),
    [
        (
            "start_in_workarea",
            123456,
            timedelta(days=40),
            "override_schedule_work_area",
            {
                "work_area_id": 123456,
                "duration": {"days": 40},
            },
        ),
    ],
)
async def test_lawn_mower_override_work_area_command(
    hass: HomeAssistant,
    aioautomower_command: str,
    extra_data1: int,
    extra_data2: timedelta,
    service: str,
    service_data: dict[str, int] | None,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower work area override commands."""
    await setup_integration(hass, mock_config_entry)
    mocked_method = getattr(mock_automower_client.commands, aioautomower_command)
    await hass.services.async_call(
        domain=DOMAIN,
        service=service,
        target={"entity_id": "lawn_mower.test_mower_1"},
        service_data=service_data,
        blocking=True,
    )
    mocked_method.assert_called_once_with(TEST_MOWER_ID, extra_data1, extra_data2)

    getattr(
        mock_automower_client.commands, aioautomower_command
    ).side_effect = ApiError("Test error")
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
    ("service", "service_data", "mower_support_wa", "exception"),
    [
        (
            "override_schedule",
            {
                "duration": {"days": 1, "hours": 12, "minutes": 30},
                "override_mode": "fly_to_moon",
            },
            False,
            MultipleInvalid,
        ),
        (
            "override_schedule_work_area",
            {
                "work_area_id": 123456,
                "duration": {"days": 40},
            },
            False,
            ServiceValidationError,
        ),
        (
            "override_schedule_work_area",
            {
                "work_area_id": 12345,
                "duration": {"days": 40},
            },
            True,
            ServiceValidationError,
        ),
    ],
)
async def test_lawn_mower_wrong_service_commands(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, int] | None,
    mower_support_wa: bool,
    exception,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    values: dict[str, MowerAttributes],
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)
    values[TEST_MOWER_ID].capabilities.work_areas = mower_support_wa
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    with pytest.raises(exception):
        await hass.services.async_call(
            domain=DOMAIN,
            service=service,
            target={"entity_id": "lawn_mower.test_mower_1"},
            service_data=service_data,
            blocking=True,
        )
