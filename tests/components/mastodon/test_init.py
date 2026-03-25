"""Tests for the Mastodon integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from mastodon.Mastodon import (
    MastodonError,
    MastodonNotFoundError,
    MastodonUnauthorizedError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.mastodon.config_flow import MastodonConfigFlow
from homeassistant.components.mastodon.const import CONF_BASE_URL, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


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


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (MastodonNotFoundError, ConfigEntryState.SETUP_RETRY),
        (MastodonUnauthorizedError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_initialization_failure(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test initialization failure."""
    mock_mastodon_client.instance_v1.side_effect = exception
    mock_mastodon_client.instance_v2.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


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


async def test_coordinator_general_error(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test general error during coordinator update makes entities unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.mastodon_trwnh_mastodon_social_bot")
    assert state is not None
    assert state.state == STATE_ON

    mock_mastodon_client.account_verify_credentials.side_effect = MastodonError

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("binary_sensor.mastodon_trwnh_mastodon_social_bot")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # No reauth flow should be triggered (unlike auth errors)
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


async def test_coordinator_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_mastodon_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test auth failure during coordinator update triggers reauth flow."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_mastodon_client.account_verify_credentials.side_effect = (
        MastodonUnauthorizedError
    )

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == mock_config_entry.entry_id
