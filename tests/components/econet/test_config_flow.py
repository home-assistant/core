"""Tests for the Econet component."""
from pyeconet.api import EcoNetApiInterface
from pyeconet.errors import InvalidCredentialsError, PyeconetError

from homeassistant.components.econet import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.async_mock import patch


async def test_bad_credentials(hass):
    """Test when provided credentials are rejected."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER

    with patch(
        "pyeconet.EcoNetApiInterface.login",
        side_effect=InvalidCredentialsError(),
    ), patch("homeassistant.components.econet.async_setup", return_value=True), patch(
        "homeassistant.components.econet.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {
            "base": "invalid_auth",
        }


async def test_generic_error_from_library(hass):
    """Test when connection fails."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER

    with patch(
        "pyeconet.EcoNetApiInterface.login",
        side_effect=PyeconetError(),
    ), patch("homeassistant.components.econet.async_setup", return_value=True), patch(
        "homeassistant.components.econet.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {
            "base": "cannot_connect",
        }


async def test_auth_worked(hass):
    """Test when provided credentials are accepted."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER

    with patch(
        "pyeconet.EcoNetApiInterface.login",
        return_value=EcoNetApiInterface,
    ), patch("homeassistant.components.econet.async_setup", return_value=True), patch(
        "homeassistant.components.econet.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_EMAIL: "admin@localhost.com",
                CONF_PASSWORD: "password0",
            },
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_EMAIL: "admin@localhost.com",
            CONF_PASSWORD: "password0",
        }
