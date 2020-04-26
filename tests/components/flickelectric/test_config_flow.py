"""Test the Flick Electric config flow."""
import asyncio

from asynctest import patch
from pyflick.authentication import AuthException

from homeassistant import config_entries, setup
from homeassistant.components.flickelectric.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flickelectric.config_flow.SimpleFlickAuth.async_get_access_token",
        return_value="123456789abcdef",
    ), patch(
        "homeassistant.components.flickelectric.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.flickelectric.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Flick Electric: test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_login(hass):
    """Test uniqueness of username."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flickelectric.config_flow.SimpleFlickAuth.async_get_access_token",
        return_value="123456789abcdef",
    ), patch(
        "homeassistant.components.flickelectric.async_setup", return_value=True
    ), patch(
        "homeassistant.components.flickelectric.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result4["type"] == "abort"
    assert result4["reason"] == "already_configured"


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flickelectric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=AuthException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username2", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flickelectric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username3", "password": "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
