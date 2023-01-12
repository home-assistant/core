"""Test smtp config flow."""
from smtplib import SMTPAuthenticationError
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.smtp.const import DOMAIN
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_CONFIG, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def smtp_setup_fixture():
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
        user_input=MOCK_USER_INPUT,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "smtp"
    assert result["data"] == MOCK_USER_INPUT


async def test_flow_username_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    new_entry = MOCK_USER_INPUT.copy()
    new_entry[CONF_NAME] = "New name"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_flow_entry_name_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate entry name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
    )

    entry.add_to_hass(hass)

    new_entry = MOCK_USER_INPUT.copy()
    new_entry[CONF_USERNAME] = "example2@mail.com"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=new_entry,
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_auth(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test when username or password provided are not valid."""

    mock_client.side_effect = SMTPAuthenticationError(0, bytes("INVALID DATA", "utf-8"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )
    assert result["type"] == FlowResultType.FORM
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
        user_input=MOCK_USER_INPUT,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_import(hass: HomeAssistant) -> None:
    """Test an import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "smtp"
    assert result["data"] == MOCK_CONFIG


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {CONF_USERNAME: "example@mail.com"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "new-password",
        },
    )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_reauth_failed(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_client.side_effect = SMTPAuthenticationError(0, bytes("INVALID DATA", "utf-8"))

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-wrong-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
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
        data=MOCK_USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=MOCK_USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_client.side_effect = ConnectionRefusedError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-wrong-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
