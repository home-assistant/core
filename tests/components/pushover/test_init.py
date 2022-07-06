"""Test pushbullet integration."""
from unittest.mock import MagicMock, patch

from pushover_complete import BadAPIRequestError
import pytest

from homeassistant.components.pushover.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_pushover():
    """Mock pushbullet."""
    with patch("homeassistant.components.pushover.PushoverAPI") as mock_client:
        mock_client.return_value._generic_post.return_value = True
        yield mock_client


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test pushover successful setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED


async def test_async_setup_entry_failed_invalid_api_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover failed setup due to invalid api key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    mock_pushover.side_effect = BadAPIRequestError("400: application token is invalid")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_failed_invalid_user_key(
    hass: HomeAssistant, mock_pushover: MagicMock
) -> None:
    """Test pushover failed setup due to invalid user key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)
    mock_pushover.side_effect = BadAPIRequestError("400: user key is invalid")
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR
