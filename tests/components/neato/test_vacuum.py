"""Test the Neato vacuum platform."""

from unittest.mock import MagicMock

from pybotvac.exceptions import NeatoRobotException
import pytest

from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_ID = "vacuum.mock_robot"


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("service", "robot_method", "translation_key"),
    [
        pytest.param(SERVICE_START, "start_cleaning", "start_failed", id="start"),
        pytest.param(SERVICE_PAUSE, "pause_cleaning", "pause_failed", id="pause"),
        pytest.param(
            SERVICE_RETURN_TO_BASE,
            "send_to_base",
            "return_to_base_failed",
            id="return_to_base",
        ),
        pytest.param(SERVICE_STOP, "stop_cleaning", "stop_failed", id="stop"),
        pytest.param(SERVICE_LOCATE, "locate", "locate_failed", id="locate"),
        pytest.param(
            SERVICE_CLEAN_SPOT,
            "start_spot_cleaning",
            "clean_spot_failed",
            id="clean_spot",
        ),
    ],
)
async def test_vacuum_action_failed(
    hass: HomeAssistant,
    mock_robot: MagicMock,
    service: str,
    robot_method: str,
    translation_key: str,
) -> None:
    """Test a failed vacuum action raises."""
    getattr(mock_robot, robot_method).side_effect = NeatoRobotException

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            VACUUM_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
