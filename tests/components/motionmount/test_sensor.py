"""Tests for the MotionMount Sensor platform."""

from unittest.mock import MagicMock, PropertyMock

from motionmount import MotionMountSystemError
import pytest

from homeassistant.core import HomeAssistant

from . import ZEROCONF_NAME

from tests.common import MockConfigEntry

MAC = bytes.fromhex("c4dd57f8a55f")


@pytest.mark.parametrize(
    "system_status",
    [
        (None, "none"),
        (MotionMountSystemError.MotorError, "motor"),
        (MotionMountSystemError.ObstructionDetected, "obstruction"),
        (MotionMountSystemError.TVWidthConstraintError, "tv_width_constraint"),
        (MotionMountSystemError.HDMICECError, "hdmi_cec"),
        (MotionMountSystemError.InternalError, "internal"),
    ],
)
async def test_error_status_sensor_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
    system_status: (MotionMountSystemError, str),
) -> None:
    """Tests the state attributes."""
    (status, state) = system_status

    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).system_status = PropertyMock(
        return_value=[status]
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == state
