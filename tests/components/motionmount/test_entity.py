"""Tests for the MotionMount Entity base."""

from unittest.mock import MagicMock, PropertyMock

from homeassistant.core import HomeAssistant

from . import ZEROCONF_NAME

from tests.common import MockConfigEntry

MAC = bytes.fromhex("c4dd57f8a55f")


async def test_entity(
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
    type(mock_motionmount_config_flow).error_status = PropertyMock(return_value=0)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "none"


async def test_entity_no_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(
        return_value=b"\x00\x00\x00\x00\x00\x00"
    )
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=True
    )
    type(mock_motionmount_config_flow).error_status = PropertyMock(return_value=0)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert hass.states.get("sensor.my_motionmount_error_status").state == "none"
