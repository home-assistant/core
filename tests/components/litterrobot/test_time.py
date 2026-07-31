"""Test the Litter-Robot time entity."""

from datetime import datetime, time
from typing import Any
from unittest.mock import MagicMock, patch

from pylitterbot import LitterRobot3
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import create_mock_account, setup_integration

from tests.common import snapshot_platform

SLEEP_START_TIME_ENTITY_ID = "time.test_sleep_mode_start_time"


@pytest.mark.freeze_time(datetime(2023, 7, 1, 12))
async def test_sleep_mode_start_time(
    hass: HomeAssistant, mock_account: MagicMock
) -> None:
    """Tests the sleep mode start time."""
    await setup_integration(hass, mock_account, TIME_DOMAIN)

    entity = hass.states.get(SLEEP_START_TIME_ENTITY_ID)
    assert entity
    assert entity.state == "17:16:00"

    robot: LitterRobot3 = mock_account.robots[0]
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: SLEEP_START_TIME_ENTITY_ID, ATTR_TIME: time(23, 0)},
        blocking=True,
    )
    robot.set_sleep_mode.assert_awaited_once_with(True, time(23, 0))


async def test_time_command_exception(
    hass: HomeAssistant, mock_account_with_side_effects: MagicMock
) -> None:
    """Test that LitterRobotException is wrapped in HomeAssistantError."""
    await setup_integration(hass, mock_account_with_side_effects, TIME_DOMAIN)

    with pytest.raises(HomeAssistantError, match="Invalid command: oops"):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SLEEP_START_TIME_ENTITY_ID, ATTR_TIME: time(23, 0)},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Litter-Robot 5 time entities."""
    with patch("homeassistant.components.litterrobot.PLATFORMS", [Platform.TIME]):
        entry = await setup_integration(hass, mock_account_with_litterrobot_5)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("entity_id", "state", "expected_args", "expected_kwargs"),
    [
        pytest.param(
            "time.test_sunday_sleep_mode_start_time",
            "22:00:00",
            (True, 90),
            {"day_of_week": 0},
            id="sunday_start_enabled",
        ),
        pytest.param(
            "time.test_wednesday_sleep_mode_end_time",
            "07:00:00",
            (True,),
            {"wake_time": 90, "day_of_week": 3},
            id="wednesday_end_enabled",
        ),
        pytest.param(
            "time.test_friday_sleep_mode_start_time",
            "23:00:00",
            (False, 90),
            {"day_of_week": 5},
            id="friday_start_preserves_disabled",
        ),
    ],
)
async def test_litter_robot_5_sleep_schedule(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
    entity_id: str,
    state: str,
    expected_args: tuple[Any, ...],
    expected_kwargs: dict[str, int],
) -> None:
    """Tests the Litter-Robot 5 per-day sleep schedule time entities."""
    await setup_integration(hass, mock_account_with_litterrobot_5, TIME_DOMAIN)

    entity = hass.states.get(entity_id)
    assert entity
    assert entity.state == state

    robot = mock_account_with_litterrobot_5.robots[0]
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: time(1, 30)},
        blocking=True,
    )
    robot.set_sleep_mode.assert_awaited_once_with(*expected_args, **expected_kwargs)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_no_sleep_schedule(
    hass: HomeAssistant,
) -> None:
    """Tests time entities when the robot reports no sleep schedule."""
    mock_account = create_mock_account(robot_data={"sleepSchedules": []}, v5=True)
    await setup_integration(hass, mock_account, TIME_DOMAIN)

    entity = hass.states.get("time.test_sunday_sleep_mode_start_time")
    assert entity
    assert entity.state == "unknown"

    robot = mock_account.robots[0]
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "time.test_sunday_sleep_mode_start_time",
            ATTR_TIME: time(22, 0),
        },
        blocking=True,
    )
    robot.set_sleep_mode.assert_awaited_once_with(False, 1320, day_of_week=0)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_litter_robot_5_set_time_failed(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Test that a rejected schedule update raises HomeAssistantError."""
    await setup_integration(hass, mock_account_with_litterrobot_5, TIME_DOMAIN)

    robot = mock_account_with_litterrobot_5.robots[0]
    robot.set_sleep_mode.return_value = False

    with pytest.raises(HomeAssistantError, match="Unable to update"):
        await hass.services.async_call(
            TIME_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "time.test_sunday_sleep_mode_start_time",
                ATTR_TIME: time(22, 0),
            },
            blocking=True,
        )


async def test_litter_robot_4_has_no_time_entities(
    hass: HomeAssistant,
    mock_account_with_litterrobot_4: MagicMock,
) -> None:
    """Test that a Litter-Robot 4 creates no time entities."""
    await setup_integration(hass, mock_account_with_litterrobot_4, TIME_DOMAIN)

    assert not hass.states.async_entity_ids(TIME_DOMAIN)
