"""Tests for the SleepIQ config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}


async def test_show_set_form(hass) -> None:
    """Test that the setup form is served."""
    with patch("sleepyq.Sleepyq.login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


async def test_login_error(hass) -> None:
    """Test we show user form with appropriate error on login failure."""
    with patch("sleepyq.Sleepyq.login", side_effect=ValueError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_success(hass) -> None:
    """Test successful flow provides entry creation data."""
    with patch("sleepyq.Sleepyq.login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_USERNAME] == USER_INPUT[CONF_USERNAME]
        assert result["data"][CONF_PASSWORD] == USER_INPUT[CONF_PASSWORD]
