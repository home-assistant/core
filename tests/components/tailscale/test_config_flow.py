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

from tests.common import MockConfigEntry

OAUTH_INPUT = {
    CONF_OAUTH_CLIENT_ID: "tskey-client-FAKE",
    CONF_OAUTH_CLIENT_SECRET: "fake-oauth-client-secret",
}

USER_INPUT = {CONF_TAILNET: "homeassistant.github", **OAUTH_INPUT}


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "homeassistant.github"
    assert result.get("data") == USER_INPUT
    assert result["result"].unique_id == "homeassistant.github"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1
    assert len(mock_tailscale_config_flow.close.mock_calls) == 1


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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_tailscale_config_flow.devices.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": reason}
    assert len(mock_setup_entry.mock_calls) == 0

    mock_tailscale_config_flow.devices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
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
        result["flow_id"], user_input=USER_INPUT
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
    assert len(mock_tailscale_config_flow.close.mock_calls) == 1


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
