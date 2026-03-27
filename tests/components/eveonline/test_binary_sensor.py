"""Test the Eve Online binary sensor platform."""

from unittest.mock import AsyncMock

from eveonline.models import CharacterOnlineStatus

from homeassistant.config_entries import ConfigEntryState
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


async def test_character_online_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the character online binary sensor shows on when online."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_online.return_value = (
        CharacterOnlineStatus(online=True)
    )

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.test_capsuleer_online")
    assert state is not None
    assert state.state == "on"


async def test_character_offline_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the character online binary sensor shows off when offline."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_character_online.return_value = (
        CharacterOnlineStatus(online=False)
    )

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.test_capsuleer_online")
    assert state is not None
    assert state.state == "off"


async def test_character_online_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the character online sensor is unavailable when data is None."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    # character_online defaults to None in conftest
    mock_eveonline_client.async_get_character_online.return_value = None

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.test_capsuleer_online")
    assert state is not None
    assert state.state == "unavailable"


async def test_server_vip_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the server VIP binary sensor reflects VIP mode."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status(
        vip=True
    )

    # Enable the disabled-by-default entity before setup.
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "binary_sensor",
        "eveonline",
        "eveonline_server_vip",
        suggested_object_id="eve_online_tranquility_vip_mode",
        disabled_by=None,
    )

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("binary_sensor.eve_online_tranquility_vip_mode")
    assert state is not None
    assert state.state == "on"
