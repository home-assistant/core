"""Tests for the MotionMount Sensor platform."""

from unittest.mock import MagicMock, PropertyMock

import motionmount

from homeassistant.core import HomeAssistant

from . import ZEROCONF_NAME

from tests.common import MockConfigEntry

MAC = bytes.fromhex("c4dd57f8a55f")


async def test_error_status_sensor_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "none"


async def test_error_status_sensor_motor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).system_status = PropertyMock(
        return_value=[motionmount.MotionMountSystemError.MotorError]
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "motor"


async def test_error_status_sensor_obstruction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).system_status = PropertyMock(
        return_value=[motionmount.MotionMountSystemError.ObstructionDetected]
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "obstruction"


async def test_error_status_sensor_tv_width_constraint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).system_status = PropertyMock(
        return_value=[motionmount.MotionMountSystemError.TVWidthConstraintError]
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert (
        hass.states.get("sensor.my_motionmount_error_status").state
        == "tv_width_constraint"
    )


async def test_error_status_sensor_hdmi_cec(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).system_status = PropertyMock(
        return_value=[motionmount.MotionMountSystemError.HDMICECError]
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "hdmi_cec"


async def test_error_status_sensor_internal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).system_status = PropertyMock(
        return_value=[motionmount.MotionMountSystemError.InternalError]
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "internal"
