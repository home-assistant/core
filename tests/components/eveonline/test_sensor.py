"""Test the Eve Online sensor platform."""

from unittest.mock import AsyncMock

from eveonline.models import SkillQueueEntry, WalletBalance

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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


async def test_server_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that server sensors are created with correct values."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status(
        players=31250
    )

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("sensor.eve_online_tranquility_players_online")
    assert state is not None
    assert state.state == "31250"


async def test_character_wallet_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the wallet balance sensor shows the correct value."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.return_value = WalletBalance(
        balance=1234567.89
    )

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "1234567.89"


async def test_character_skill_queue_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that the skill queue count sensor shows the correct value."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_skill_queue.return_value = [
        SkillQueueEntry(
            skill_id=3436,
            finished_level=5,
            queue_position=0,
            start_date=None,
            finish_date=None,
        ),
        SkillQueueEntry(
            skill_id=3437,
            finished_level=4,
            queue_position=1,
            start_date=None,
            finish_date=None,
        ),
    ]

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("sensor.test_capsuleer_skill_queue")
    assert state is not None
    assert state.state == "2"


async def test_unavailable_character_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that sensors with unavailable data are marked unavailable."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    # wallet_balance defaults to None in conftest → sensor should be unavailable
    mock_eveonline_client.async_get_wallet_balance.return_value = None

    await _setup_integration(hass, mock_config_entry, mock_eveonline_client)

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unavailable"
