"""Test the Velux config flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest
from pyvlx import PyVLXException

from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DUMMY_DATA: dict[str, Any] = {
    CONF_HOST: "127.0.0.1",
    CONF_PASSWORD: "NotAStrongPassword",
}

PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH = (
    "homeassistant.components.velux.config_flow.PyVLX.connect"
)
PYVLX_CONFIG_FLOW_CLASS_PATH = "homeassistant.components.velux.config_flow.PyVLX"

error_types_to_test: list[tuple[Exception, str]] = [
    (PyVLXException("DUMMY"), "cannot_connect"),
    (Exception("DUMMY"), "unknown"),
]

pytest.mark.usefixtures("mock_setup_entry")


async def test_user_success(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True) as client_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        client_mock.return_value.disconnect.assert_called_once()
        client_mock.return_value.connect.assert_called_once()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DUMMY_DATA[CONF_HOST]
        assert result["data"] == DUMMY_DATA


@pytest.mark.parametrize(("error", "error_name"), error_types_to_test)
async def test_user_errors(
    hass: HomeAssistant, error: Exception, error_name: str
) -> None:
    """Test starting a flow by user but with exceptions."""
    with patch(
        PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH, side_effect=error
    ) as connect_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        connect_mock.assert_called_once()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error_name}


async def test_import_valid_config(hass: HomeAssistant) -> None:
    """Test import initialized flow with valid config."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DUMMY_DATA,
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DUMMY_DATA[CONF_HOST]
        assert result["data"] == DUMMY_DATA


@pytest.mark.parametrize("flow_source", [SOURCE_IMPORT, SOURCE_USER])
async def test_flow_duplicate_entry(hass: HomeAssistant, flow_source: str) -> None:
    """Test import initialized flow with a duplicate entry."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title=DUMMY_DATA[CONF_HOST], data=DUMMY_DATA
        )

        conf_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": flow_source},
            data=DUMMY_DATA,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(("error", "error_name"), error_types_to_test)
async def test_import_errors(
    hass: HomeAssistant, error: Exception, error_name: str
) -> None:
    """Test import initialized flow with exceptions."""
    with patch(
        PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH,
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DUMMY_DATA,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == error_name
