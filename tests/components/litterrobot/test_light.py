"""Test the Litter-Robot light entity."""

from unittest.mock import MagicMock, patch

from pylitterbot.exceptions import InvalidCommandException
from pylitterbot.robot.litterrobot4 import NightLightMode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import create_mock_account, setup_integration

from tests.common import snapshot_platform

NIGHT_LIGHT_ENTITY_ID = "light.test_night_light"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Litter-Robot 5 light entities."""
    with patch("homeassistant.components.litterrobot.PLATFORMS", [Platform.LIGHT]):
        entry = await setup_integration(hass, mock_account_with_litterrobot_5)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_turn_on_brightness(
    hass: HomeAssistant, mock_account_with_litterrobot_5: MagicMock
) -> None:
    """Test setting the night light brightness, preserving mode and color."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    robot = mock_account_with_litterrobot_5.robots[0]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: NIGHT_LIGHT_ENTITY_ID, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    robot.set_night_light_settings.assert_awaited_once_with(
        mode=NightLightMode.AUTO, brightness=100, color="#FFFFFF"
    )


async def test_turn_on_color(
    hass: HomeAssistant, mock_account_with_litterrobot_5: MagicMock
) -> None:
    """Test setting the night light color, preserving mode and brightness."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    robot = mock_account_with_litterrobot_5.robots[0]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: NIGHT_LIGHT_ENTITY_ID, ATTR_RGB_COLOR: (255, 0, 0)},
        blocking=True,
    )
    robot.set_night_light_settings.assert_awaited_once_with(
        mode=NightLightMode.AUTO, brightness=50, color="#FF0000"
    )


async def test_turn_on_from_off_switches_on(hass: HomeAssistant) -> None:
    """Test turning on a night light that is off switches the mode to on."""
    mock_account = create_mock_account(
        robot_data={
            "nightLightSettings": {
                "brightness": 50,
                "color": "#FFFFFF",
                "mode": "OFF",
            }
        },
        v5=True,
    )
    await setup_integration(hass, mock_account, LIGHT_DOMAIN)

    entity = hass.states.get(NIGHT_LIGHT_ENTITY_ID)
    assert entity
    assert entity.state == "off"

    robot = mock_account.robots[0]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: NIGHT_LIGHT_ENTITY_ID},
        blocking=True,
    )
    robot.set_night_light_settings.assert_awaited_once_with(
        mode=NightLightMode.ON, brightness=50, color="#FFFFFF"
    )


async def test_turn_off(
    hass: HomeAssistant, mock_account_with_litterrobot_5: MagicMock
) -> None:
    """Test turning off the night light."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    robot = mock_account_with_litterrobot_5.robots[0]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: NIGHT_LIGHT_ENTITY_ID},
        blocking=True,
    )
    robot.set_night_light_settings.assert_awaited_once_with(mode=NightLightMode.OFF)


async def test_command_exception(hass: HomeAssistant) -> None:
    """Test that a LitterRobotException is wrapped in HomeAssistantError."""
    mock_account = create_mock_account(
        side_effect=InvalidCommandException("Invalid command: oops"), v5=True
    )
    await setup_integration(hass, mock_account, LIGHT_DOMAIN)

    with pytest.raises(HomeAssistantError, match="Invalid command: oops"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: NIGHT_LIGHT_ENTITY_ID},
            blocking=True,
        )


async def test_litter_robot_4_has_no_light(
    hass: HomeAssistant, mock_account_with_litterrobot_4: MagicMock
) -> None:
    """Test that a Litter-Robot 4 creates no light entities."""
    await setup_integration(hass, mock_account_with_litterrobot_4, LIGHT_DOMAIN)

    assert not hass.states.async_entity_ids(LIGHT_DOMAIN)
