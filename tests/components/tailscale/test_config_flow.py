"""Tests for the Tailscale config flow."""

from unittest.mock import AsyncMock, MagicMock

from tailscale import TailscaleAuthenticationError, TailscaleConnectionError

from homeassistant.components.tailscale.const import CONF_TAILNET, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TAILNET: "homeassistant.github",
            CONF_API_KEY: "tskey-FAKE",
        },
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "homeassistant.github"
    assert result2.get("data") == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-FAKE",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


async def test_full_flow_with_authentication_error(
    hass: HomeAssistant,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow with incorrect API key.

    This tests tests a full config flow, with a case the user enters an invalid
    Tailscale API key, but recovers by entering the correct one.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_tailscale_config_flow.devices.side_effect = TailscaleAuthenticationError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_TAILNET: "homeassistant.github",
            CONF_API_KEY: "tskey-INVALID",
        },
    )

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert result2.get("errors") == {"base": "invalid_auth"}

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1

    mock_tailscale_config_flow.devices.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            CONF_TAILNET: "homeassistant.github",
            CONF_API_KEY: "tskey-VALID",
        },
    )

    assert result3.get("type") is FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "homeassistant.github"
    assert result3.get("data") == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-VALID",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 2


async def test_connection_error(
    hass: HomeAssistant, mock_tailscale_config_flow: MagicMock
) -> None:
    """Test API connection error."""
    mock_tailscale_config_flow.devices.side_effect = TailscaleConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_TAILNET: "homeassistant.github",
            CONF_API_KEY: "tskey-FAKE",
        },
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}

    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauthentication configuration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "tskey-REAUTH"},
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-REAUTH",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1


async def test_reauth_with_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tailscale_config_flow: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauthentication configuration flow with an authentication error.

    This tests tests a reauth flow, with a case the user enters an invalid
    API key, but recover by entering the correct one.
    """
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    mock_tailscale_config_flow.devices.side_effect = TailscaleAuthenticationError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "tskey-INVALID"},
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "reauth_confirm"
    assert result2.get("errors") == {"base": "invalid_auth"}

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 1

    mock_tailscale_config_flow.devices.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={CONF_API_KEY: "tskey-VALID"},
    )
    await hass.async_block_till_done()

    assert result3.get("type") is FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_TAILNET: "homeassistant.github",
        CONF_API_KEY: "tskey-VALID",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_tailscale_config_flow.devices.mock_calls) == 2


async def test_reauth_api_error(
    hass: HomeAssistant,
    mock_tailscale_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test API error during reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    mock_tailscale_config_flow.devices.side_effect = TailscaleConnectionError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_KEY: "tskey-VALID"},
    )
    await hass.async_block_till_done()

    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "reauth_confirm"
    assert result2.get("errors") == {"base": "cannot_connect"}
