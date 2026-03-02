"""Test the Litter-Robot light entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from pylitterbot import LitterRobot5

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

LIGHT_ENTITY_ID = "light.test_night_light"


async def test_night_light_state(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Litter-Robot 5 night light entity state."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state
    # Mock data has mode=Auto, so light is "on"
    assert state.state == "on"
    # brightness=50 -> round(50 * 255 / 100) = 128
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    # color=#FFFFFF -> (255, 255, 255)
    assert state.attributes[ATTR_RGB_COLOR] == (255, 255, 255)

    entry = entity_registry.async_get(LIGHT_ENTITY_ID)
    assert entry


async def test_night_light_turn_on_with_color(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Test turning on the night light with RGB color."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    robot: LitterRobot5 = mock_account_with_litterrobot_5.robots[0]

    with patch(
        "homeassistant.components.litterrobot.light.async_update_night_light_settings",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_update:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID, ATTR_RGB_COLOR: (255, 0, 0)},
            blocking=True,
        )
        mock_update.assert_called_once_with(robot, color="FF0000")

    # Verify optimistic state update
    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)


async def test_night_light_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Test turning on the night light with brightness."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    robot: LitterRobot5 = mock_account_with_litterrobot_5.robots[0]

    with patch(
        "homeassistant.components.litterrobot.light.async_update_night_light_settings",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_update:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID, ATTR_BRIGHTNESS: 191},
            blocking=True,
        )
        # 191 * 100 / 255 = 74.9 -> round = 75
        mock_update.assert_called_once_with(robot, brightness=75)

    # Verify optimistic state update
    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state
    assert state.attributes[ATTR_BRIGHTNESS] == 191


async def test_night_light_turn_off(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Test turning off the night light."""
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    robot: LitterRobot5 = mock_account_with_litterrobot_5.robots[0]

    with patch(
        "homeassistant.components.litterrobot.light.async_update_night_light_settings",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_update:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
            blocking=True,
        )
        mock_update.assert_called_once_with(robot, mode="Off")

    # Verify optimistic state update
    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state
    assert state.state == "off"


async def test_night_light_turn_on_from_off(
    hass: HomeAssistant,
    mock_account_with_litterrobot_5: MagicMock,
) -> None:
    """Test turning on the night light when mode is OFF."""
    robot_data = {"nightLightSettings": {"brightness": 50, "color": "#FF0000", "mode": "Off"}}
    mock_account_with_litterrobot_5.robots[0] = LitterRobot5(
        data={**__import__("tests.components.litterrobot.common", fromlist=["ROBOT_5_DATA"]).ROBOT_5_DATA, **robot_data},
        account=mock_account_with_litterrobot_5,
    )
    await setup_integration(hass, mock_account_with_litterrobot_5, LIGHT_DOMAIN)

    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state
    assert state.state == "off"

    robot = mock_account_with_litterrobot_5.robots[0]

    with patch(
        "homeassistant.components.litterrobot.light.async_update_night_light_settings",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_update:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: LIGHT_ENTITY_ID},
            blocking=True,
        )
        mock_update.assert_called_once_with(robot, mode="On")

    # Verify optimistic state update
    state = hass.states.get(LIGHT_ENTITY_ID)
    assert state
    assert state.state == "on"
