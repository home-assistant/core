"""Tests for honeywell config flow."""
from unittest.mock import patch

import somecomfort

from homeassistant import data_entry_flow
from homeassistant.components.honeywell import config_flow
from homeassistant.core import HomeAssistant


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the config form is shown."""
    flow = config_flow.HoneywellConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test that an error message is shown on login fail."""
    flow = config_flow.HoneywellConfigFlow()
    flow.hass = hass

    with patch(
        "somecomfort.SomeComfort",
        side_effect=somecomfort.AuthError,
    ):
        result = await flow.async_step_user(
            user_input={"username": "fake", "password": "user"}
        )
        assert result["errors"] == {"base": "auth_error"}


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the config entry is created."""
    flow = config_flow.HoneywellConfigFlow()
    flow.hass = hass

    with patch(
        "somecomfort.SomeComfort",
    ):
        result = await flow.async_step_user(
            user_input={"username": "fake", "password": "user"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
