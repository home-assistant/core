"""Tests for the Whois config flow."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from whois.exceptions import (
    FailedParsingWhoisOutput,
    UnknownDateFormat,
    UnknownTld,
    WhoisCommandFailed,
)

from homeassistant.components.whois.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_whois_config_flow: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DOMAIN: "Example.com"},
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Example.com"
    assert result2.get("data") == {CONF_DOMAIN: "example.com"}

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "throw,reason",
    [
        (UnknownTld, "unknown_tld"),
        (FailedParsingWhoisOutput, "unexpected_response"),
        (UnknownDateFormat, "unknown_date_format"),
        (WhoisCommandFailed, "whois_command_failed"),
    ],
)
async def test_full_flow_with_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_whois_config_flow: MagicMock,
    throw: Exception,
    reason: str,
) -> None:
    """Test the full user configuration flow with an error.

    This tests tests a full config flow, with an error happening; allowing
    the user to fix the error and try again.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    mock_whois_config_flow.side_effect = throw
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_DOMAIN: "Example.com"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {"base": reason}
    assert "flow_id" in result2

    assert len(mock_setup_entry.mock_calls) == 0
    assert len(mock_whois_config_flow.mock_calls) == 1

    mock_whois_config_flow.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={CONF_DOMAIN: "Example.com"},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Example.com"
    assert result3.get("data") == {CONF_DOMAIN: "example.com"}

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_whois_config_flow.mock_calls) == 2


async def test_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_whois_config_flow: MagicMock,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_DOMAIN: "HOME-Assistant.io"},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"

    assert len(mock_setup_entry.mock_calls) == 0
