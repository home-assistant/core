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
    CONF_OAUTH_CLIENT_SECRET: "tskey-client-FAKE-SECRET",
}
API_KEY_INPUT = {CONF_API_KEY: "tskey-FAKE"}


async def _async_reach_credentials_menu(hass: HomeAssistant) -> str:
    """Start a user flow and return the flow ID at the credentials menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_TAILNET: "homeassistant.github"}
    )
    assert result.get("type") is FlowResultType.MENU
    assert result.get("step_id") == "credentials"
    return result["flow_id"]


@pytest.mark.parametrize(
    ("menu_option", "user_input"),
    [("oauth", OAUTH_INPUT), ("api_key", API_KEY_INPUT)],
)
async def test_full_user_flow(
    hass: HomeAssistant,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
    menu_option: str,
    user_input: dict[str, str],
) -> None:
    """Test the full user configuration flow, for both credential types."""
    flow_id = await _async_reach_credentials_menu(hass)

    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": menu_option}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == menu_option

    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=user_input
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "homeassistant.github"
    assert result.get("data") == {
        CONF_TAILNET: "homeassistant.github",
        **user_input,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


@pytest.mark.parametrize(
    ("menu_option", "user_input"),
    [("oauth", OAUTH_INPUT), ("api_key", API_KEY_INPUT)],
)
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
    menu_option: str,
    user_input: dict[str, str],
    side_effect: Exception,
    reason: str,
) -> None:
    """Test the user flow recovering from an error entering credentials."""
    flow_id = await _async_reach_credentials_menu(hass)

    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": menu_option}
    )

    mock_tailscale_config_flow.devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=user_input
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == menu_option
    assert result.get("errors") == {"base": reason}
    assert len(mock_setup_entry.mock_calls) == 0

    mock_tailscale_config_flow.devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=user_input
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
    """Test reauthentication of an entry using an API access token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "tskey-REAUTH"}
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-REAUTH",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


async def test_reauth_flow_oauth(
    hass: HomeAssistant,
    mock_config_entry_oauth: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication of an entry using OAuth client credentials."""
    mock_config_entry_oauth.add_to_hass(hass)

    result = await mock_config_entry_oauth.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm_oauth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry_oauth.data == {
        CONF_TAILNET: "homeassistant.github",
        **OAUTH_INPUT,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


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
    side_effect: Exception,
    reason: str,
) -> None:
    """Test the reauth flow recovering from an error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_tailscale_config_flow.devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "tskey-INVALID"}
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert result.get("errors") == {"base": reason}
    assert len(mock_setup_entry.mock_calls) == 0

    mock_tailscale_config_flow.devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "tskey-VALID"}
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-VALID",
    }


async def test_reconfigure_flow_migrates_to_oauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test an API access token entry can be migrated to an OAuth client."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], OAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"

    # The API access token must not be left behind in the entry.
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        **OAUTH_INPUT,
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
    side_effect: Exception,
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

    # The original credentials must be left untouched on failure.
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-MOCK",
    }


async def test_oauth_flow_closes_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test validating OAuth credentials does not leave the client open.

    This exercises the actual library rather than mocking it: validating
    credentials triggers a token request, which schedules a refresh task that
    has to be cancelled again. A lingering task is caught by verify_cleanup.
    """
    aioclient_mock.post(
        "https://api.tailscale.com/api/v2/oauth/token",
        json={"access_token": "tskey-api-TEMPORARY", "expires_in": 3600},
    )
    aioclient_mock.get(
        "https://api.tailscale.com/api/v2/tailnet/homeassistant.github/devices?fields=all",
        text=await async_load_fixture(hass, "devices.json", DOMAIN),
    )

    flow_id = await _async_reach_credentials_menu(hass)
    await hass.config_entries.flow.async_configure(
        flow_id, user_input={"next_step_id": "oauth"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, user_input=OAUTH_INPUT
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {CONF_TAILNET: "homeassistant.github", **OAUTH_INPUT}
