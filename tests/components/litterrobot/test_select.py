"""Test the Litter-Robot select entity."""

from unittest.mock import AsyncMock, MagicMock

from pylitterbot import LitterRobot3, LitterRobot4, LitterRobot5
from pylitterbot.robot.litterrobot4 import NightLightMode
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import create_mock_account, setup_integration

SELECT_ENTITY_ID = "select.test_clean_cycle_wait_time_minutes"


async def test_wait_time_select(
    hass: HomeAssistant, mock_account, entity_registry: er.EntityRegistry
) -> None:
    """Tests the wait time select entity."""
    await setup_integration(hass, mock_account, SELECT_DOMAIN)

    select = hass.states.get(SELECT_ENTITY_ID)
    assert select

    entity_entry = entity_registry.async_get(SELECT_ENTITY_ID)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    data = {ATTR_ENTITY_ID: SELECT_ENTITY_ID}

    for count, wait_time in enumerate(LitterRobot3.VALID_WAIT_TIMES):
        data[ATTR_OPTION] = wait_time

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

        assert mock_account.robots[0].set_wait_time.call_count == count + 1


async def test_invalid_wait_time_select(hass: HomeAssistant, mock_account) -> None:
    """Tests the wait time select entity with invalid value."""
    await setup_integration(hass, mock_account, SELECT_DOMAIN)

    select = hass.states.get(SELECT_ENTITY_ID)
    assert select

    data = {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "10"}

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )
    assert not mock_account.robots[0].set_wait_time.called


@pytest.mark.parametrize(
    ("entity_id", "initial_value", "robot_command"),
    [
        ("select.test_globe_brightness", "medium", "set_night_light_brightness"),
        ("select.test_globe_light", "off", "set_night_light_mode"),
        ("select.test_panel_brightness", "medium", "set_panel_brightness"),
    ],
)
async def test_litterrobot_4_select(
    hass: HomeAssistant,
    mock_account_with_litterrobot_4: MagicMock,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    initial_value: str,
    robot_command: str,
) -> None:
    """Tests a Litter-Robot 4 select entity."""
    await setup_integration(hass, mock_account_with_litterrobot_4, SELECT_DOMAIN)

    select = hass.states.get(entity_id)
    assert select
    assert len(select.attributes[ATTR_OPTIONS]) == 3
    assert select.state == initial_value

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    data = {ATTR_ENTITY_ID: entity_id}

    robot: LitterRobot4 = mock_account_with_litterrobot_4.robots[0]
    setattr(robot, robot_command, AsyncMock(return_value=True))

    for count, option in enumerate(select.attributes[ATTR_OPTIONS]):
        data[ATTR_OPTION] = option

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

        assert getattr(robot, robot_command).call_count == count + 1


async def test_select_command_exception(
    hass: HomeAssistant, mock_account_with_side_effects: MagicMock
) -> None:
    """Test that LitterRobotException is wrapped in HomeAssistantError."""
    await setup_integration(hass, mock_account_with_side_effects, SELECT_DOMAIN)

    with pytest.raises(HomeAssistantError, match="Invalid command: oops"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: "7"},
            blocking=True,
        )


async def test_litterrobot_5_globe_light(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests the Litter-Robot 5 globe light (night light mode) select entity."""
    entity_id = "select.test_globe_light"
    await setup_integration(hass, mock_account_with_litterrobot_5, SELECT_DOMAIN)

    select = hass.states.get(entity_id)
    assert select
    assert len(select.attributes[ATTR_OPTIONS]) == 3
    assert select.state == "auto"

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    data = {ATTR_ENTITY_ID: entity_id}

    robot: LitterRobot5 = mock_account_with_litterrobot_5.robots[0]

    for option in select.attributes[ATTR_OPTIONS]:
        data[ATTR_OPTION] = option

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

    assert robot.set_night_light_mode.call_count == 3
    robot.set_night_light_mode.assert_any_call(NightLightMode.OFF)
    robot.set_night_light_mode.assert_any_call(NightLightMode.ON)
    robot.set_night_light_mode.assert_any_call(NightLightMode.AUTO)


async def test_litterrobot_5_night_light_preset(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests the Litter-Robot 5 night light preset select entity."""
    entity_id = "select.test_night_light_preset"
    await setup_integration(hass, mock_account_with_litterrobot_5, SELECT_DOMAIN)

    select = hass.states.get(entity_id)
    assert select
    assert len(select.attributes[ATTR_OPTIONS]) == 7
    # The fixture color #FFFFFF matches the white preset.
    assert select.state == "white"

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    robot: LitterRobot5 = mock_account_with_litterrobot_5.robots[0]
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "cyan"},
        blocking=True,
    )
    # Selecting a preset writes the color while preserving mode and brightness.
    robot.set_night_light_settings.assert_awaited_once_with(
        mode=NightLightMode.AUTO, brightness=50, color=(0, 255, 255)
    )


async def test_litterrobot_5_night_light_preset_custom_color(
    hass: HomeAssistant,
) -> None:
    """A color outside the preset list leaves the preset select unknown."""
    mock_account = create_mock_account(
        robot_data={
            "nightLightSettings": {
                "brightness": 50,
                "color": "#123456",
                "mode": "Auto",
            }
        },
        v5=True,
    )
    await setup_integration(hass, mock_account, SELECT_DOMAIN)

    select = hass.states.get("select.test_night_light_preset")
    assert select
    assert select.state == STATE_UNKNOWN


async def test_litterrobot_5_panel_brightness(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests the Litter-Robot 5 panel brightness select entity."""
    entity_id = "select.test_panel_brightness"
    await setup_integration(hass, mock_account_with_litterrobot_5, SELECT_DOMAIN)

    select = hass.states.get(entity_id)
    assert select
    assert len(select.attributes[ATTR_OPTIONS]) == 3
    assert select.state == "medium"

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    data = {ATTR_ENTITY_ID: entity_id}

    robot: LitterRobot5 = mock_account_with_litterrobot_5.robots[0]
    robot.set_panel_brightness = AsyncMock(return_value=True)

    for count, option in enumerate(select.attributes[ATTR_OPTIONS]):
        data[ATTR_OPTION] = option

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

        assert robot.set_panel_brightness.call_count == count + 1


async def test_litterrobot_5_globe_brightness(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests the Litter-Robot 5 globe brightness select entity."""
    entity_id = "select.test_globe_brightness"
    # A stored brightness of 100 maps to the LR5 "medium" level (the LR5 renders
    # brightness non-monotonically, so low/medium/high map to 10/100/75).
    mock_account = create_mock_account(
        robot_data={
            "nightLightSettings": {
                "brightness": 100,
                "color": "#FFFFFF",
                "mode": "Auto",
            }
        },
        v5=True,
    )
    await setup_integration(hass, mock_account, SELECT_DOMAIN)

    select = hass.states.get(entity_id)
    assert select
    assert len(select.attributes[ATTR_OPTIONS]) == 3
    assert select.state == "medium"

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.CONFIG

    robot: LitterRobot5 = mock_account.robots[0]

    # Each option must set the eye-calibrated percentage for that LR5 level.
    for option, brightness in (("low", 10), ("medium", 100), ("high", 75)):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
            blocking=True,
        )
        robot.set_night_light_brightness.assert_awaited_with(brightness)

    assert robot.set_night_light_brightness.await_count == 3


async def test_litterrobot_5_globe_brightness_unmapped(hass: HomeAssistant) -> None:
    """A brightness with no matching level leaves globe brightness unknown."""
    # The default LR5 fixture brightness (50) maps to no low/medium/high level.
    mock_account = create_mock_account(v5=True)
    await setup_integration(hass, mock_account, SELECT_DOMAIN)

    select = hass.states.get("select.test_globe_brightness")
    assert select
    assert select.state == STATE_UNKNOWN
