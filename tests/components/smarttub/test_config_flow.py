"""Test the smarttub config flow."""
from unittest.mock import patch

from smarttub import LoginFailed

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.smarttub.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.smarttub.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.smarttub.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
        )

        assert result2["type"] == "create_entry"
        assert result2["title"] == "test-email"
        assert result2["data"] == {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        }
        await hass.async_block_till_done()
        mock_setup.assert_called_once()
        mock_setup_entry.assert_called_once()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "test-email2", CONF_PASSWORD: "test-password2"}
    )
    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"


async def test_form_invalid_auth(hass, smarttub_api):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    smarttub_api.login.side_effect = LoginFailed

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth(hass, smarttub_api):
    """Test reauthentication flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "test-email", CONF_PASSWORD: "test-password"}
    )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-email"
    config_entry = result2["result"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "test-email3", CONF_PASSWORD: "test-password3"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_EMAIL] == "test-email3"
    assert config_entry.data[CONF_PASSWORD] == "test-password3"
