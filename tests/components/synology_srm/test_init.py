"""Test Synology SRM setup process."""

from unittest.mock import MagicMock, patch

import pytest
from synology_srm.http import SynologyApiError

from homeassistant.components import synology_srm
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with (
        patch("synology_srm.Client") as mock_api,
    ):
        yield mock_api


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=synology_srm.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


async def test_hub_connection_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Test setup fails due to connection error."""
    entry = MockConfigEntry(
        domain=synology_srm.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = SynologyApiError(500, "error")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_hub_authentication_error(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test setup fails due to authentication error."""
    entry = MockConfigEntry(
        domain=synology_srm.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = SynologyApiError(401, "invalid user name or password")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading an entry."""
    entry = MockConfigEntry(
        domain=synology_srm.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
