"""Test the Neato vacuum platform."""

from unittest.mock import MagicMock

from pybotvac.exceptions import NeatoRobotException
import pytest

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, VacuumService
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

ENTITY_ID = "vacuum.mock_robot"


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("service", "robot_method", "translation_key"),
    [
        pytest.param(VacuumService.START, "start_cleaning", "start_failed", id="start"),
        pytest.param(VacuumService.PAUSE, "pause_cleaning", "pause_failed", id="pause"),
        pytest.param(
            VacuumService.RETURN_TO_BASE,
            "send_to_base",
            "return_to_base_failed",
            id="return_to_base",
        ),
        pytest.param(VacuumService.STOP, "stop_cleaning", "stop_failed", id="stop"),
        pytest.param(VacuumService.LOCATE, "locate", "locate_failed", id="locate"),
        pytest.param(
            VacuumService.CLEAN_SPOT,
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
            {TargetKey.ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
