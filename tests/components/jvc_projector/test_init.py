"""Tests for JVC Projector config entry."""

from unittest.mock import AsyncMock

from jvcprojector import JvcProjectorAuthError, JvcProjectorConnectError

from homeassistant.components.jvc_projector.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MOCK_MAC

from tests.common import MockConfigEntry


async def test_init(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test initialization."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_MAC)})
    assert device is not None
    assert device.identifiers == {(DOMAIN, MOCK_MAC)}


async def test_unload_config_entry(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_integration: MockConfigEntry,
) -> None:
    """Test config entry loading and unloading."""
    mock_config_entry = mock_integration
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_config_entry_connect_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry with connect error."""
    mock_device.connect.side_effect = JvcProjectorConnectError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_auth_error(
    hass: HomeAssistant,
    mock_device: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry with auth error."""
    mock_device.connect.side_effect = JvcProjectorAuthError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
