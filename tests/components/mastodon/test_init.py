"""Tests for the Mastodon integration."""

from unittest.mock import AsyncMock

from mastodon.Mastodon import MastodonNotFoundError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mastodon.config_flow import MastodonConfigFlow
from homeassistant.components.mastodon.const import CONF_BASE_URL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


async def test_initialization_failure(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test initialization failure."""
    mock_mastodon_client.instance_v1.side_effect = MastodonNotFoundError
    mock_mastodon_client.instance_v2.side_effect = MastodonNotFoundError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_integration_fallback_to_instance_v1(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test full flow where instance_v2 fails and falls back to instance_v1."""
    mock_mastodon_client.instance_v2.side_effect = MastodonNotFoundError(
        "Instance API v2 not found"
    )

    await setup_integration(hass, mock_config_entry)

    mock_mastodon_client.instance_v2.assert_called_once()
    mock_mastodon_client.instance_v1.assert_called_once()


async def test_migrate(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
) -> None:
    """Test migration."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BASE_URL: "https://mastodon.social",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
            CONF_ACCESS_TOKEN: "access_token",
        },
        title="@trwnh@mastodon.social",
        unique_id="client_id",
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check migration was successful
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data == {
        CONF_BASE_URL: "https://mastodon.social",
        CONF_CLIENT_ID: "client_id",
        CONF_CLIENT_SECRET: "client_secret",
        CONF_ACCESS_TOKEN: "access_token",
    }
    assert config_entry.version == MastodonConfigFlow.VERSION
    assert config_entry.minor_version == MastodonConfigFlow.MINOR_VERSION
    assert config_entry.unique_id == "trwnh_mastodon_social"
