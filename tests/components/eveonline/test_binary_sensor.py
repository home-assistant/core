"""Tests for the Eve Online binary sensor platform."""

from unittest.mock import AsyncMock

from eveonline.models import CharacterOnlineStatus

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import mock_server_status

from tests.common import MockConfigEntry


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
) -> None:
    """Set up the eveonline integration with mocked data."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_character_online_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test character online binary sensor shows on when character is online."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_online.return_value = (
        CharacterOnlineStatus(online=True)
    )
    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.test_capsuleer_connectivity")
    assert state is not None
    assert state.state == STATE_ON


async def test_character_offline_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test character online binary sensor shows off when character is offline."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_online.return_value = (
        CharacterOnlineStatus(online=False)
    )
    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.test_capsuleer_connectivity")
    assert state is not None
    assert state.state == STATE_OFF


async def test_character_online_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test character online shows unavailable when endpoint fails."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_online.return_value = None
    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.test_capsuleer_connectivity")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_server_vip_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    setup_credentials: None,
) -> None:
    """Test server VIP binary sensor (disabled by default)."""
    entity_registry.async_get_or_create(
        "binary_sensor",
        "eveonline",
        "eveonline_server_vip",
        config_entry=mock_config_entry,
        disabled_by=None,
        suggested_object_id="eve_online_tranquility_vip_mode",
    )
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status(
        vip=True,
    )
    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.eve_online_tranquility_vip_mode")
    assert state is not None
    assert state.state == STATE_ON
