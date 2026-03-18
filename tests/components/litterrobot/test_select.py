"""Test the Litter-Robot select entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot import LitterRobot3, LitterRobot4, LitterRobot5
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

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

    with patch(
        "homeassistant.components.litterrobot.select.async_update_night_light_settings",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_update:
        for option in select.attributes[ATTR_OPTIONS]:
            data[ATTR_OPTION] = option

            await hass.services.async_call(
                SELECT_DOMAIN,
                SERVICE_SELECT_OPTION,
                data,
                blocking=True,
            )

        assert mock_update.call_count == 3
        # Verify the mode value is capitalized to match API format (On/Off/Auto)
        mock_update.assert_any_call(robot, mode="Off")
        mock_update.assert_any_call(robot, mode="On")
        mock_update.assert_any_call(robot, mode="Auto")


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
    setattr(robot, "set_panel_brightness", AsyncMock(return_value=True))

    for count, option in enumerate(select.attributes[ATTR_OPTIONS]):
        data[ATTR_OPTION] = option

        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            data,
            blocking=True,
        )

        assert robot.set_panel_brightness.call_count == count + 1

    # Verify globe_brightness select is not created for LR5
    assert hass.states.get("select.test_globe_brightness") is None
