"""Test Mikrotik setup process."""

from unittest.mock import MagicMock, patch

from librouteros.exceptions import ConnectionClosed, LibRouterosError
import pytest

from homeassistant.components import mikrotik
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with (
        patch("librouteros.create_transport"),
        patch("librouteros.Api.readResponse") as mock_api,
    ):
        yield mock_api


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


async def test_hub_connection_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test setup fails due to connection error."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_authentication_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test setup fails due to authentication error."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = LibRouterosError("invalid user name or password")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
