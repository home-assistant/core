"""Test the smarttub config flow."""

from unittest.mock import patch

from smarttub import LoginFailed

from homeassistant import config_entries
from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.smarttub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
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
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()


async def test_form_invalid_auth(hass: HomeAssistant, smarttub_api) -> None:
    """Test we handle invalid auth."""
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


async def test_reauth_success(hass: HomeAssistant, smarttub_api, account) -> None:
    """Test reauthentication flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        unique_id=account.id,
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data=mock_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "test-email3", CONF_PASSWORD: "test-password3"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data[CONF_EMAIL] == "test-email3"
    assert mock_entry.data[CONF_PASSWORD] == "test-password3"


async def test_reauth_wrong_account(hass: HomeAssistant, smarttub_api, account) -> None:
    """Test reauthentication flow if the user enters credentials for a different already-configured account."""
    mock_entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email1", CONF_PASSWORD: "test-password1"},
        unique_id=account.id,
    )
    mock_entry1.add_to_hass(hass)

    mock_entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test-email2", CONF_PASSWORD: "test-password2"},
        unique_id="mockaccount2",
    )
    mock_entry2.add_to_hass(hass)

    # we try to reauth account #2, and the user successfully authenticates to account #1
    account.id = mock_entry1.unique_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry2.unique_id,
            "entry_id": mock_entry2.entry_id,
        },
        data=mock_entry2.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "test-email1", CONF_PASSWORD: "test-password1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
