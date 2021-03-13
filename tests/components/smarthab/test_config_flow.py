"""Test the SmartHab config flow."""
from unittest.mock import patch

import pysmarthab

from homeassistant import config_entries, setup
from homeassistant.components.smarthab import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("pysmarthab.SmartHab.async_login"), patch(
        "pysmarthab.SmartHab.is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.smarthab.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.smarthab.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "mock@example.com", CONF_PASSWORD: "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "mock@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "mock@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("pysmarthab.SmartHab.async_login"), patch(
        "pysmarthab.SmartHab.is_logged_in", return_value=False
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "mock@example.com", CONF_PASSWORD: "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_service_error(hass):
    """Test we handle service errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pysmarthab.SmartHab.async_login",
        side_effect=pysmarthab.RequestFailedException(42),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "mock@example.com", CONF_PASSWORD: "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "service"}


async def test_form_unknown_error(hass):
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pysmarthab.SmartHab.async_login",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_EMAIL: "mock@example.com", CONF_PASSWORD: "test-password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_import(hass):
    """Test import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    imported_conf = {
        CONF_EMAIL: "mock@example.com",
        CONF_PASSWORD: "test-password",
    }

    with patch("pysmarthab.SmartHab.async_login"), patch(
        "pysmarthab.SmartHab.is_logged_in", return_value=True
    ), patch(
        "homeassistant.components.smarthab.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.smarthab.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=imported_conf
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "mock@example.com"
    assert result["data"] == {
        CONF_EMAIL: "mock@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
