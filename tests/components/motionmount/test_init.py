"""Tests for the MotionMount init."""

from unittest.mock import MagicMock, PropertyMock

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import ZEROCONF_NAME

from tests.common import MockConfigEntry

MAC = bytes.fromhex("c4dd57f8a55f")


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_failed_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    mock_motionmount_config_flow.connect.side_effect = TimeoutError()
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_wrong_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=False
    )
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, sources={SOURCE_REAUTH}))


async def test_setup_entry_wrong_pin(
    hass: HomeAssistant,
    mock_config_entry_with_pin: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Tests the state attributes."""
    mock_config_entry_with_pin.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    type(mock_motionmount_config_flow).is_authenticated = PropertyMock(
        return_value=False
    )
    assert not await hass.config_entries.async_setup(
        mock_config_entry_with_pin.entry_id
    )

    assert mock_config_entry_with_pin.state is ConfigEntryState.SETUP_ERROR
    assert any(
        mock_config_entry_with_pin.async_get_active_flows(hass, sources={SOURCE_REAUTH})
    )


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_motionmount_config_flow: MagicMock,
) -> None:
    """Test entries are unloaded correctly."""
    mock_config_entry.add_to_hass(hass)

    type(mock_motionmount_config_flow).name = PropertyMock(return_value=ZEROCONF_NAME)
    type(mock_motionmount_config_flow).mac = PropertyMock(return_value=MAC)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_motionmount_config_flow.disconnect.call_count == 1
