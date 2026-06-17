"""Test the SMTP config flow."""

from smtplib import SMTPAuthenticationError
from socket import gaierror
from ssl import SSLCertVerificationError
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.smtp.const import (
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState, FlowType
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import USER_INPUT

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
            **USER_INPUT,
            CONF_ENCRYPTION: encryption,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant"
    assert result["data"] == {
        **USER_INPUT,
        CONF_ENCRYPTION: encryption,
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
        USER_INPUT,
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
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    smtp.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Assistant"
    assert result["data"] == USER_INPUT
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


@pytest.mark.usefixtures("smtp")
async def test_options_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test options flow."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TIMEOUT: 10,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_TIMEOUT: 10,
    }


@pytest.mark.usefixtures("smtp")
async def test_form_reconfigure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_SENDER_NAME: "New sender name",
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert config_entry.data == {
        **USER_INPUT,
        CONF_SENDER_NAME: "New sender name",
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }

    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("smtp")
async def test_form_reconfigure_already_configured(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow already configured."""

    MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant",
        data={
            **USER_INPUT,
            CONF_SENDER: "already_configured@example.com",
        },
        entry_id="987654321",
    ).add_to_hass(hass)

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_SENDER: "already_configured@example.com",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert len(hass.config_entries.async_entries()) == 2


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
@pytest.mark.usefixtures("smtp")
async def test_form_reconfigure_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    smtp: MagicMock,
    exception: Exception,
    text_error: str,
) -> None:
    """Test reconfigure flow connection errors."""

    smtp.login.side_effect = exception

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_SENDER_NAME: "New sender name",
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    smtp.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **USER_INPUT,
            CONF_SENDER_NAME: "New sender name",
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert config_entry.data == {
        **USER_INPUT,
        CONF_SENDER_NAME: "New sender name",
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.usefixtures("smtp")
async def test_form_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test reauth flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data == {
        **USER_INPUT,
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }

    assert len(hass.config_entries.async_entries()) == 1


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
@pytest.mark.usefixtures("smtp")
async def test_form_reauth_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    smtp: MagicMock,
    exception: Exception,
    text_error: str,
) -> None:
    """Test reauth flow connection errors."""

    smtp.login.side_effect = exception

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    smtp.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert config_entry.data == {
        **USER_INPUT,
        CONF_USERNAME: "new-username",
        CONF_PASSWORD: "new-password",
    }
    assert len(hass.config_entries.async_entries()) == 1
