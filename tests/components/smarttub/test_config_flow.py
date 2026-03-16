"""Test the smarttub config flow."""

from unittest.mock import patch

import pytest
from smarttub import LoginFailed

from homeassistant import config_entries
from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Mock the integration setup."""
    with patch(
        "homeassistant.components.smarttub.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


async def test_user_flow(hass: HomeAssistant, mock_setup_entry, account) -> None:
    """Test the user config flow creates an entry with correct data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == {
        CONF_EMAIL: "test-email",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == account.id
    mock_setup_entry.assert_called_once()


async def test_form_invalid_auth(
    hass: HomeAssistant, smarttub_api, mock_setup_entry
) -> None:
    """Test we handle invalid auth and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    smarttub_api.login.side_effect = LoginFailed

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    smarttub_api.login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_success(hass: HomeAssistant, smarttub_api, config_entry) -> None:
    """Test reauthentication flow."""
    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "test-email3", CONF_PASSWORD: "test-password3"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_EMAIL] == "test-email3"
    assert config_entry.data[CONF_PASSWORD] == "test-password3"


async def test_reauth_wrong_account(
    hass: HomeAssistant, smarttub_api, account, config_entry
) -> None:
    """Test reauthentication flow if the user enters credentials for a different already-configured account."""
    config_entry.add_to_hass(hass)

    mock_entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email2", CONF_PASSWORD: "test-password2"},
        unique_id="mockaccount2",
    )
    mock_entry2.add_to_hass(hass)

    # we try to reauth account #2, and the user successfully authenticates to account #1
    account.id = config_entry.unique_id
    result = await mock_entry2.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "test-email1", CONF_PASSWORD: "test-password1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
