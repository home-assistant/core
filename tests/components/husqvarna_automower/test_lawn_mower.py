"""Tests for lawn_mower module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aioautomower.exceptions import ApiException
from aioautomower.model import Tasks
from aioautomower.utils import mower_list_to_dictionary_dataclass
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
        ("GOING_HOME", "IN_OPERATION", LawnMowerActivity.RETURNING),
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
    extra_data: timedelta,
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
    mocked_method = AsyncMock()
    setattr(mock_automower_client.commands, aioautomower_command, mocked_method)
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
) -> None:
    """Test lawn_mower commands."""
    await setup_integration(hass, mock_config_entry)
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
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


@pytest.mark.parametrize(
    ("entity", "mower_id", "service_data", "output"),
    [
        (
            "lawn_mower.test_mower_1",
            TEST_MOWER_ID,
            {
                "mode": "overwrite",
                "start": "17:00:00",
                "end": "20:00:00",
                "monday": True,
                "tuesday": True,
                "wednesday": True,
                "thursday": True,
                "friday": True,
                "saturday": False,
                "sunday": False,
                "work_area_id": 0,
            },
            Tasks.from_dict(
                {
                    "tasks": [
                        {
                            "start": 1020,
                            "duration": 180,
                            "monday": True,
                            "tuesday": True,
                            "wednesday": True,
                            "thursday": True,
                            "friday": True,
                            "saturday": False,
                            "sunday": False,
                            "workAreaId": 0,
                        },
                    ]
                }
            ),
        ),
        (
            "lawn_mower.test_mower_1",
            TEST_MOWER_ID,
            {
                "mode": "remove",
                "start": "01:00:00",
                "end": "09:00:00",
                "monday": True,
                "tuesday": True,
                "wednesday": False,
                "thursday": True,
                "friday": False,
                "saturday": True,
                "sunday": False,
                "work_area_id": 654321,
            },
            Tasks.from_dict(
                {
                    "tasks": [
                        {
                            "start": 0,
                            "duration": 480,
                            "monday": False,
                            "tuesday": True,
                            "wednesday": False,
                            "thursday": True,
                            "friday": False,
                            "saturday": True,
                            "sunday": False,
                            "workAreaId": 654321,
                        },
                    ]
                }
            ),
        ),
        (
            "lawn_mower.test_mower_1",
            TEST_MOWER_ID,
            {
                "mode": "add",
                "start": "10:00:00",
                "end": "11:00:00",
                "monday": True,
                "tuesday": False,
                "wednesday": False,
                "thursday": False,
                "friday": False,
                "saturday": False,
                "sunday": False,
                "work_area_id": 654321,
            },
            Tasks.from_dict(
                {
                    "tasks": [
                        {
                            "start": 0,
                            "duration": 480,
                            "monday": False,
                            "tuesday": True,
                            "wednesday": False,
                            "thursday": True,
                            "friday": False,
                            "saturday": True,
                            "sunday": False,
                            "workAreaId": 654321,
                        },
                        {
                            "start": 60,
                            "duration": 480,
                            "monday": True,
                            "tuesday": True,
                            "wednesday": False,
                            "thursday": True,
                            "friday": False,
                            "saturday": True,
                            "sunday": False,
                            "workAreaId": 654321,
                        },
                        {
                            "start": 600,
                            "duration": 60,
                            "monday": True,
                            "tuesday": False,
                            "wednesday": False,
                            "thursday": False,
                            "friday": False,
                            "saturday": False,
                            "sunday": False,
                            "workAreaId": 654321,
                        },
                    ]
                }
            ),
        ),
        (
            "lawn_mower.test_mower_2",
            "1234",
            {
                "mode": "add",
                "start": "10:00:00",
                "end": "11:00:00",
                "monday": True,
                "tuesday": False,
                "wednesday": False,
                "thursday": False,
                "friday": False,
                "saturday": False,
                "sunday": False,
            },
            Tasks.from_dict(
                {
                    "tasks": [
                        {
                            "start": 120,
                            "duration": 49,
                            "monday": True,
                            "tuesday": False,
                            "wednesday": False,
                            "thursday": False,
                            "friday": False,
                            "saturday": False,
                            "sunday": False,
                        },
                        {
                            "start": 600,
                            "duration": 60,
                            "monday": True,
                            "tuesday": False,
                            "wednesday": False,
                            "thursday": False,
                            "friday": False,
                            "saturday": False,
                            "sunday": False,
                        },
                    ]
                }
            ),
        ),
        (
            "lawn_mower.test_mower_2",
            "1234",
            {
                "mode": "remove",
                "start": "02:00",
                "end": "02:49",
                "monday": True,
                "tuesday": False,
                "wednesday": False,
                "thursday": False,
                "friday": False,
                "saturday": False,
                "sunday": False,
            },
            Tasks.from_dict({"tasks": []}),
        ),
    ],
)
async def test_lawn_mower_set_schedule_command(
    hass: HomeAssistant,
    output: Tasks,
    entity: str,
    mower_id: str,
    service_data: dict[str, int] | None,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower work area override commands."""
    await setup_integration(hass, mock_config_entry)
    mocked_method = AsyncMock()
    setattr(mock_automower_client.commands, "set_calendar", mocked_method)
    await hass.services.async_call(
        domain=DOMAIN,
        service="set_schedule",
        target={"entity_id": entity},
        service_data=service_data,
        blocking=True,
    )
    mocked_method.assert_called_once_with(mower_id, output)

    getattr(mock_automower_client.commands, "set_calendar").side_effect = ApiException(
        "Test error"
    )
    with pytest.raises(
        HomeAssistantError,
        match="Failed to send command: Test error",
    ):
        await hass.services.async_call(
            domain=DOMAIN,
            service="set_schedule",
            target={"entity_id": entity},
            service_data=service_data,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data", "fail_message"),
    [
        (
            "set_schedule",
            {
                "mode": "remove",
                "start": "11:11:00",
                "end": "12:00:00",
                "monday": True,
                "tuesday": True,
                "wednesday": False,
                "thursday": True,
                "friday": False,
                "saturday": True,
                "sunday": False,
                "work_area_id": 654321,
            },
            "Calendar entry not found. Can't be removed",
        ),
        (
            "set_schedule",
            {
                "mode": "add",
                "start": "19:00",
                "end": "23:59",
                "monday": True,
                "tuesday": False,
                "wednesday": True,
                "thursday": False,
                "friday": True,
                "saturday": False,
                "sunday": False,
                "work_area_id": 123456,
            },
            "Calendar entry already exists",
        ),
        (
            "set_schedule",
            {
                "mode": "overwrite",
                "start": "11:11",
                "end": "11:11",
                "monday": True,
                "tuesday": False,
                "wednesday": True,
                "thursday": False,
                "friday": True,
                "saturday": False,
                "sunday": False,
                "work_area_id": 0,
            },
            "Start must be at least one minute before end",
        ),
    ],
)
async def test_lawn_mower_set_schedule_command_service_validation(
    hass: HomeAssistant,
    service: str,
    service_data: dict[str, int] | None,
    fail_message: str,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lawn_mower work area override commands."""
    await setup_integration(hass, mock_config_entry)
    mocked_method = AsyncMock()
    setattr(mock_automower_client.commands, "set_calendar", mocked_method)

    with pytest.raises(
        ServiceValidationError,
        match=fail_message,
    ):
        await hass.services.async_call(
            domain=DOMAIN,
            service=service,
            target={"entity_id": "lawn_mower.test_mower_1"},
            service_data=service_data,
            blocking=True,
        )
