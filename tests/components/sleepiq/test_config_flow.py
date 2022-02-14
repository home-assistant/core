"""Tests for the SleepIQ config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

SLEEPIQ_CONFIG = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}


async def test_import(hass: HomeAssistant) -> None:
    """Test that we can import a config entry."""
    with patch("sleepyq.Sleepyq.login"):
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: SLEEPIQ_CONFIG})
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data[CONF_USERNAME] == SLEEPIQ_CONFIG[CONF_USERNAME]
    assert entry.data[CONF_PASSWORD] == SLEEPIQ_CONFIG[CONF_PASSWORD]


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    with patch("sleepyq.Sleepyq.login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


async def test_login_error(hass: HomeAssistant) -> None:
    """Test we show user form with appropriate error on login failure."""
    with patch("sleepyq.Sleepyq.login", side_effect=ValueError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=SLEEPIQ_CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_success(hass: HomeAssistant) -> None:
    """Test successful flow provides entry creation data."""
    with patch("sleepyq.Sleepyq.login"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=SLEEPIQ_CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_USERNAME] == SLEEPIQ_CONFIG[CONF_USERNAME]
        assert result["data"][CONF_PASSWORD] == SLEEPIQ_CONFIG[CONF_PASSWORD]
