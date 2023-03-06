"""Test the Velux config flow."""
from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest
from pyvlx import PyVLXException
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

DUMMY_DATA: dict[str, Any] = {
    CONF_HOST: "127.0.0.1",
    CONF_PASSWORD: "NotAStrongPassword",
}

PYVLX_CONNECT_FUNCTION_PATH = "pyvlx.PyVLX.connect"
PYVLX_DISCONNECT_FUNCTION_PATH = "pyvlx.PyVLX.disconnect"


pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_schema(hass: HomeAssistant) -> None:
    """Test that the user step uses the correct Schema."""
    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["data_schema"] == vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
        }
    )


async def test_user_connection_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with an unexpected exception."""

    with patch(
        PYVLX_CONNECT_FUNCTION_PATH, side_effect=PyVLXException("DUMMY")
    ) as connect_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        connect_mock.assert_called_once()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_unknown_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with an unexpected exception."""
    with patch(
        PYVLX_CONNECT_FUNCTION_PATH, side_effect=Exception("DUMMY")
    ) as connect_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        connect_mock.assert_called_once()

        assert result["type"] == data_entry_flow.FlowResultType.ABORT


async def test_user_success(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(PYVLX_CONNECT_FUNCTION_PATH) as connect_mock, patch(
        PYVLX_DISCONNECT_FUNCTION_PATH
    ) as disconnect_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        connect_mock.assert_called_once()
        disconnect_mock.assert_called_once()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DUMMY_DATA[CONF_HOST]


async def test_import(hass: HomeAssistant) -> None:
    """Test import initialized flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=DUMMY_DATA,
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DUMMY_DATA[CONF_HOST]
    assert result["data"] == DUMMY_DATA
