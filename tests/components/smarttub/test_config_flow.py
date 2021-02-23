"""Test the smarttub config flow."""
from unittest.mock import patch

from smarttub import LoginFailed

from homeassistant import config_entries
from homeassistant.components.smarttub.const import DOMAIN


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
            {"email": "test-email", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "test-email"
    assert result2["data"] == {
        "email": "test-email",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    mock_setup.assert_called_once()
    mock_setup_entry.assert_called_once()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"email": "test-email2", "password": "test-password2"}
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
        {"email": "test-email", "password": "test-password"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
