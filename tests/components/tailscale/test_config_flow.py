"""Tests for the Tailscale config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from tailscale import TailscaleAuthenticationError, TailscaleConnectionError

from homeassistant.components.tailscale.const import (
    CONF_OAUTH_CLIENT_ID,
    CONF_OAUTH_CLIENT_SECRET,
    CONF_TAILNET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, async_load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

OAUTH_INPUT = {
    CONF_OAUTH_CLIENT_ID: "tskey-client-FAKE",
    CONF_OAUTH_CLIENT_SECRET: "fake-oauth-client-secret",
}


async def _async_reach_oauth_form(hass: HomeAssistant) -> str:
    """Start a user flow and return the flow ID at the OAuth credentials form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TAILNET: "homeassistant.github"}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "oauth"
    return result["flow_id"]


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow."""
    flow_id = await _async_reach_oauth_form(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=OAUTH_INPUT
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "homeassistant.github"
    assert result.get("data") == {CONF_TAILNET: "homeassistant.github", **OAUTH_INPUT}

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (TailscaleAuthenticationError, "invalid_auth"),
        (TailscaleConnectionError, "cannot_connect"),
    ],
)
async def test_full_flow_with_error(
    hass: HomeAssistant,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the user flow recovering from an error entering credentials."""
    flow_id = await _async_reach_oauth_form(hass)

    mock_tailscale_config_flow.devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=OAUTH_INPUT
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "oauth"
    assert result.get("errors") == {"base": reason}
    assert len(mock_setup_entry.mock_calls) == 0

    mock_tailscale_config_flow.devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=OAUTH_INPUT
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 2


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the tailnet is only allowed to be configured once."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TAILNET: "homeassistant.github"}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication of an entry using OAuth client credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        **OAUTH_INPUT,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


async def test_reauth_flow_migrates_api_key_entry(
    hass: HomeAssistant,
    mock_config_entry_api_key: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication migrates a legacy API access token entry to OAuth."""
    mock_config_entry_api_key.add_to_hass(hass)

    result = await mock_config_entry_api_key.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry_api_key.data == {
        CONF_TAILNET: "homeassistant.github",
        **OAUTH_INPUT,
    }
    assert CONF_API_KEY not in mock_config_entry_api_key.data


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (TailscaleAuthenticationError, "invalid_auth"),
        (TailscaleConnectionError, "cannot_connect"),
    ],
)
async def test_reauth_with_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the reauth flow recovering from an error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_tailscale_config_flow.devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert result.get("errors") == {"base": reason}
    assert len(mock_setup_entry.mock_calls) == 0

    mock_tailscale_config_flow.devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        **OAUTH_INPUT,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
) -> None:
    """Test reconfiguring an entry's OAuth client credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    new_input = {
        CONF_OAUTH_CLIENT_ID: "tskey-client-NEW",
        CONF_OAUTH_CLIENT_SECRET: "new-oauth-client-secret",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        **new_input,
    }
    assert CONF_API_KEY not in mock_config_entry.data

    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (TailscaleAuthenticationError, "invalid_auth"),
        (TailscaleConnectionError, "cannot_connect"),
    ],
)
async def test_reconfigure_with_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    side_effect: type[Exception],
    reason: str,
) -> None:
    """Test the reconfigure flow recovering from an error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_tailscale_config_flow.devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"
    assert result.get("errors") == {"base": reason}

    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        CONF_OAUTH_CLIENT_ID: "tskey-client-MOCK",
        CONF_OAUTH_CLIENT_SECRET: "mock-oauth-client-secret",
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_oauth_flow_closes_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test validating OAuth credentials does not leave the client open.

    This exercises the actual library rather than mocking it: validating
    credentials triggers a token request, which schedules a token-expiration
    task that has to be cancelled again. A lingering task is caught by
    verify_cleanup.
    """
    aioclient_mock.post(
        "https://api.tailscale.com/api/v2/oauth/token",
        json={"access_token": "tskey-api-TEMPORARY", "expires_in": 3600},
    )
    aioclient_mock.get(
        "https://api.tailscale.com/api/v2/tailnet/homeassistant.github/devices?fields=all",
        text=await async_load_fixture(hass, "devices.json", DOMAIN),
    )

    flow_id = await _async_reach_oauth_form(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=OAUTH_INPUT
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_TAILNET: "homeassistant.github", **OAUTH_INPUT}
