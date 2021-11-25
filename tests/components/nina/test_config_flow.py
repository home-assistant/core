"""Test the Nina config flow."""
import json
from typing import Any, Dict
from unittest.mock import patch

from pynina import ApiError

from homeassistant import data_entry_flow
from homeassistant.components.nina.const import (
    CONF_FILTER_CORONA,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from tests.common import load_fixture

DUMMY_DATA: Dict[str, Any] = {
    CONF_MESSAGE_SLOTS: 5,
    CONF_REGIONS + "1": ["095760000000_0", "095760000000_1"],
    CONF_REGIONS + "2": ["010610000000_0", "010610000000_1"],
    CONF_REGIONS + "3": ["071320000000_0", "071320000000_1"],
    CONF_REGIONS + "4": ["071380000000_0", "071380000000_1"],
    CONF_REGIONS + "5": ["072320000000_0", "072320000000_1"],
    CONF_REGIONS + "6": ["081270000000_0", "081270000000_1"],
    CONF_FILTER_CORONA: True,
}

DUMMY_RESPONSE: Dict[str, Any] = json.loads(load_fixture("nina/sample_regions.json"))


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        return_value=DUMMY_RESPONSE,
    ):

        result: Dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"


async def test_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=ApiError("Could not connect to Api"),
    ):

        result: Dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_unexpected_exception(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with an unexpected exception."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=Exception("DUMMY"),
    ):

        result: Dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_step_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        return_value=DUMMY_RESPONSE,
    ):

        result: Dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "NINA"


async def test_step_user_no_selection(hass: HomeAssistant) -> None:
    """Test starting a flow by user with no selection."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        return_value=DUMMY_RESPONSE,
    ):

        result: Dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "no_selection"}


async def test_step_user_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow by user but it was already configured."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        return_value=DUMMY_RESPONSE,
    ):
        result: Dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
