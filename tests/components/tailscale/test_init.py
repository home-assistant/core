"""Tests for the Tailscale integration."""

from unittest.mock import ANY, MagicMock, patch

from tailscale import TailscaleAuthenticationError, TailscaleConnectionError
from tailscale.models import Devices

from homeassistant.components.tailscale.const import (
    CONF_OAUTH_CLIENT_ID,
    CONF_OAUTH_CLIENT_SECRET,
    CONF_TAILNET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale: MagicMock,
) -> None:
    """Test the Tailscale configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale: MagicMock,
) -> None:
    """Test the Tailscale configuration entry not ready."""
    mock_tailscale.devices.side_effect = TailscaleConnectionError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_tailscale.devices.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale: MagicMock,
) -> None:
    """Test trigger reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    mock_tailscale.devices.side_effect = TailscaleAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


async def test_api_key_entry_triggers_migration_reauth(
    hass: HomeAssistant,
    mock_config_entry_api_key: MockConfigEntry,
) -> None:
    """Test a legacy API access token entry is migrated to OAuth via reauth."""
    mock_config_entry_api_key.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_api_key.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_api_key.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry_api_key.entry_id


async def test_setup_with_oauth_client_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry configured with an OAuth client sets the client up as such."""
    with patch(
        "homeassistant.components.tailscale.coordinator.Tailscale", autospec=True
    ) as tailscale_mock:
        tailscale_mock.return_value.devices.return_value = Devices.from_json(
            await async_load_fixture(hass, "devices.json", DOMAIN)
        ).devices

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The library is handed the OAuth credentials, not an API access token.
    assert tailscale_mock.call_args.kwargs == {
        "session": ANY,
        "oauth_client_id": mock_config_entry.data[CONF_OAUTH_CLIENT_ID],
        "oauth_client_secret": mock_config_entry.data[CONF_OAUTH_CLIENT_SECRET],
        "tailnet": mock_config_entry.data[CONF_TAILNET],
    }


async def test_oauth_access_token_is_requested(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the OAuth client credentials are exchanged for an access token."""
    aioclient_mock.post(
        "https://api.tailscale.com/api/v2/oauth/token",
        json={"access_token": "tskey-api-TEMPORARY", "expires_in": 3600},
    )
    aioclient_mock.get(
        "https://api.tailscale.com/api/v2/tailnet/homeassistant.github/devices?fields=all",
        text=await async_load_fixture(hass, "devices.json", DOMAIN),
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    token_request = aioclient_mock.mock_calls[0]
    assert token_request[2] == {
        "client_id": "tskey-client-MOCK",
        "client_secret": "mock-oauth-client-secret",
    }

    devices_request = aioclient_mock.mock_calls[1]
    assert devices_request[3]["Authorization"] == "Bearer tskey-api-TEMPORARY"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_oauth_client_closed_when_setup_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the token-expiration task is cancelled when setup fails."""
    aioclient_mock.post(
        "https://api.tailscale.com/api/v2/oauth/token",
        json={"access_token": "tskey-api-TEMPORARY", "expires_in": 3600},
    )
    aioclient_mock.get(
        "https://api.tailscale.com/api/v2/tailnet/homeassistant.github/devices?fields=all",
        status=500,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
