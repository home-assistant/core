"""Tests for honeywell config flow."""
from unittest.mock import patch

import somecomfort

from homeassistant import data_entry_flow
from homeassistant.components.honeywell.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant

FAKE_CONFIG = {
    "username": "fake",
    "password": "user",
    "away_cool_temperature": 88,
    "away_heat_temperature": 61,
}


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the config form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test that an error message is shown on login fail."""
    with patch(
        "somecomfort.SomeComfort",
        side_effect=somecomfort.AuthError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=FAKE_CONFIG
        )
        assert result["errors"] == {"base": "invalid_auth"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the config entry is created."""
    with patch(
        "somecomfort.SomeComfort",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=FAKE_CONFIG
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == FAKE_CONFIG


async def test_async_step_import(hass: HomeAssistant) -> None:
    """Test that the import step works."""
    with patch(
        "somecomfort.SomeComfort",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=FAKE_CONFIG
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == FAKE_CONFIG
