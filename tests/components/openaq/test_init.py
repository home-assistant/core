"""Test OpenAQ initialization."""

from unittest.mock import AsyncMock, patch

from openaq import ServerError

from homeassistant.components.openaq.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import API_KEY

from tests.common import MockConfigEntry


async def test_setup_success(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_openaq_client
    assert len(mock_config_entry.runtime_data.coordinators) == 1


async def test_setup_retry_on_first_refresh_failure(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retry when first coordinator refresh fails."""
    mock_openaq_client.locations.latest.side_effect = ServerError("API error")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_closes_client(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading OpenAQ closes the client."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_openaq_client.close.assert_awaited_once()


async def test_update_listener_reloads_entry(
    hass: HomeAssistant,
    mock_openaq_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry updates reload the entry."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        hass.config_entries.async_update_entry(
            mock_config_entry,
            data={CONF_API_KEY: "new-api-key"},
        )
        await hass.async_block_till_done()

    mock_reload.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_setup_without_locations(
    hass: HomeAssistant, mock_openaq_client: AsyncMock
) -> None:
    """Test setup before any location subentries are configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
    )

    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.coordinators == {}
