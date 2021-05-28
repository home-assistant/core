"""Test the Rademacher HomePilot config flow."""
from unittest.mock import patch

from pyhomepilot.auth import (  # pylint:disable=redefined-builtin
    AuthError,
    ConnectionError,
)
from pytest import raises

from homeassistant import config_entries, setup
from homeassistant.components.homepilot.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.homepilot.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

TEST_USER_INPUT = {
    CONF_HOST: "192.168.1.16",
    CONF_PASSWORD: "test-password",
}


async def test_validate_input_invalid_auth(hass):
    """Test we receive an invalid auth error."""
    with patch(
        "pyhomepilot.auth.Auth.async_login",
        side_effect=AuthError(None, OSError()),
    ), raises(InvalidAuth):
        await validate_input(hass, TEST_USER_INPUT)


async def test_validate_input_cannot_connect(hass):
    """Test we receive a cannot connect error."""
    with patch(
        "pyhomepilot.auth.Auth.async_login",
        side_effect=ConnectionError(None, OSError()),
    ), raises(CannotConnect):
        await validate_input(hass, TEST_USER_INPUT)


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    with patch("pyhomepilot.auth.Auth.async_login", return_value=True,), patch(
        "pyhomepilot.api.HomePilotAPI.async_get_system_name",
        return_value="bridge",
    ), patch(
        "homeassistant.components.homepilot.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "bridge"
    assert result2["data"] == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.homepilot.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.homepilot.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass):
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.homepilot.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
