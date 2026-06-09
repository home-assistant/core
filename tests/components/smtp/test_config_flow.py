"""Test the SMTP config flow."""

from smtplib import SMTPAuthenticationError
from socket import gaierror
from ssl import SSLCertVerificationError
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.smtp.const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.config_entries import SOURCE_USER, FlowType
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("smtp", "smtp_ssl")
@pytest.mark.parametrize("encryption", ["tls", "starttls"])
async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, encryption: str
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SENDER: "email@example.com",
            CONF_SENDER_NAME: "Home Assistant",
            CONF_SERVER: "mail.example.com",
            CONF_PORT: 587,
            CONF_ENCRYPTION: encryption,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant"
    assert result["data"] == {
        CONF_SENDER: "email@example.com",
        CONF_SENDER_NAME: "Home Assistant",
        CONF_SERVER: "mail.example.com",
        CONF_PORT: 587,
        CONF_ENCRYPTION: encryption,
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_VERIFY_SSL: True,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    await hass.async_block_till_done(wait_background_tasks=True)
    subentry_flows = hass.config_entries.subentries.async_progress()
    assert len(subentry_flows) == 1
    assert result["next_flow"][0] == FlowType.CONFIG_SUBENTRIES_FLOW

    result = await hass.config_entries.subentries.async_configure(
        result["next_flow"][1],
        user_input={CONF_NAME: "Recipient", CONF_RECIPIENT: "recipient@example.com"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Recipient"
    assert result["unique_id"] == "recipient@example.com"


@pytest.mark.usefixtures("smtp")
async def test_form_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when entry is already configured."""

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SENDER: "email@example.com",
            CONF_SENDER_NAME: "Home Assistant",
            CONF_SERVER: "mail.example.com",
            CONF_PORT: 587,
            CONF_ENCRYPTION: "tls",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "text_error"),
    [
        (SMTPAuthenticationError(0, ""), "invalid_auth"),
        (ConnectionRefusedError, "cannot_connect"),
        (gaierror, "cannot_connect"),
        (SSLCertVerificationError, "invalid_cert"),
        (ValueError, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    smtp: MagicMock,
    exception: Exception,
    text_error: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    smtp.login.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SENDER: "email@example.com",
            CONF_SENDER_NAME: "Home Assistant",
            CONF_SERVER: "mail.example.com",
            CONF_PORT: 587,
            CONF_ENCRYPTION: "starttls",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    smtp.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SENDER: "email@example.com",
            CONF_SENDER_NAME: "Home Assistant",
            CONF_SERVER: "mail.example.com",
            CONF_PORT: 587,
            CONF_ENCRYPTION: "starttls",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_VERIFY_SSL: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant"
    assert result["data"] == {
        CONF_SENDER: "email@example.com",
        CONF_SENDER_NAME: "Home Assistant",
        CONF_SERVER: "mail.example.com",
        CONF_PORT: 587,
        CONF_ENCRYPTION: "starttls",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_VERIFY_SSL: True,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("smtp")
async def test_form_recipient_already_configured(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test we abort when subentry is already configured."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Rick Astley",
            CONF_RECIPIENT: "recipient@example.com",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
