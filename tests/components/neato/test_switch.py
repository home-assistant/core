"""Test the Neato switch platform."""

from unittest.mock import MagicMock

from pybotvac.exceptions import NeatoRobotException
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_ID = "switch.mock_robot_schedule"


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("service", "robot_method", "translation_key"),
    [
        pytest.param(
            SERVICE_TURN_ON, "enable_schedule", "enable_schedule_failed", id="turn_on"
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            "disable_schedule",
            "disable_schedule_failed",
            id="turn_off",
        ),
    ],
)
async def test_switch_action_failed(
    hass: HomeAssistant,
    mock_robot: MagicMock,
    service: str,
    robot_method: str,
    translation_key: str,
) -> None:
    """Test a failed schedule switch action raises."""
    getattr(mock_robot, robot_method).side_effect = NeatoRobotException

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
