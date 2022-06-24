"""Test smtp config flow."""
from smtplib import SMTPAuthenticationError
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.smtp.const import DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def simplepush_setup_fixture():
    """Patch smtp setup entry."""
    with patch("homeassistant.components.smtp.async_setup_entry", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_client():
    """Patch smtp client."""
    with patch(
        "homeassistant.components.smtp.config_flow.get_smtp_client"
    ) as mock_client:
        yield mock_client


async def test_flow_successful(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "smtp"
    assert result["data"] == MOCK_CONFIG


async def test_flow_sender_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate sender email."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="sender@email.com",
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_user_name_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="sender@email.com",
    )

    entry.add_to_hass(hass)

    new_entry = MOCK_CONFIG.copy()
    new_entry[CONF_SENDER] = "sender2@email.com"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_input(hass: HomeAssistant) -> None:
    """Test when sender or reciptient fields are not valid addresses."""
    invalid_entry = MOCK_CONFIG.copy()
    invalid_entry[CONF_SENDER] = "abc"
    invalid_entry[CONF_RECIPIENT] = "recipient"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_entry,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {
        CONF_SENDER: "invalid_email",
        CONF_RECIPIENT: "invalid_email",
    }


async def test_invalid_auth(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test when username or password provided are not valid."""

    mock_client.side_effect = SMTPAuthenticationError(0, bytes("INVALID DATA", "utf-8"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }


async def test_conn_error(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test when connection error is raised."""

    mock_client.side_effect = ConnectionRefusedError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test an import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "smtp"
    assert result["data"] == MOCK_CONFIG


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {CONF_USERNAME: "username"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "new-password",
        },
    )

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    mock_client.side_effect = SMTPAuthenticationError(0, bytes("INVALID DATA", "utf-8"))

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-wrong-password",
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }


async def test_reauth_failed_conn_error(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_CONFIG,
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    mock_client.side_effect = ConnectionRefusedError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-wrong-password",
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
