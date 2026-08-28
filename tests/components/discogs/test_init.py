"""Test Discogs integration init."""

from unittest.mock import MagicMock, patch

import discogs_client

from homeassistant.components.discogs.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import MOCK_TOKEN, MOCK_USERNAME

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.discogs.coordinator.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_failure(hass: HomeAssistant) -> None:
    """Test setup entry triggers reauth on 401."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={CONF_TOKEN: MOCK_TOKEN},
        unique_id=MOCK_USERNAME,
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.identity.side_effect = discogs_client.exceptions.HTTPError(
        "Unauthorized", 401
    )

    with patch(
        "homeassistant.components.discogs.coordinator.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(entry.async_get_active_flows(hass, {"reauth"}))


async def test_setup_entry_transient_failure(hass: HomeAssistant) -> None:
    """Test setup entry retries on transient HTTP error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={CONF_TOKEN: MOCK_TOKEN},
        unique_id=MOCK_USERNAME,
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.identity.side_effect = discogs_client.exceptions.HTTPError(
        "Service Unavailable", 503
    )

    with patch(
        "homeassistant.components.discogs.coordinator.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.discogs.coordinator.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
