"""Test the Nina config flow."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

from pynina import ApiError

from homeassistant import data_entry_flow
from homeassistant.components.nina.const import (
    CONF_FILTER_CORONA,
    CONF_MESSAGE_SLOTS,
    CONF_REGIONS,
    CONST_REGION_A_TO_D,
    CONST_REGION_E_TO_H,
    CONST_REGION_I_TO_L,
    CONST_REGION_M_TO_Q,
    CONST_REGION_R_TO_U,
    CONST_REGION_V_TO_Z,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mocked_request_function

from tests.common import MockConfigEntry, load_fixture

DUMMY_DATA: dict[str, Any] = {
    CONF_MESSAGE_SLOTS: 5,
    CONST_REGION_A_TO_D: ["095760000000_0", "095760000000_1"],
    CONST_REGION_E_TO_H: ["010610000000_0", "010610000000_1"],
    CONST_REGION_I_TO_L: ["071320000000_0", "071320000000_1"],
    CONST_REGION_M_TO_Q: ["071380000000_0", "071380000000_1"],
    CONST_REGION_R_TO_U: ["072320000000_0", "072320000000_1"],
    CONST_REGION_V_TO_Z: ["081270000000_0", "081270000000_1"],
    CONF_FILTER_CORONA: True,
}

DUMMY_RESPONSE_REGIONS: dict[str, Any] = json.loads(
    load_fixture("sample_regions.json", "nina")
)
DUMMY_RESPONSE_WARNIGNS: dict[str, Any] = json.loads(
    load_fixture("sample_warnings.json", "nina")
)


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"


async def test_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=ApiError("Could not connect to Api"),
    ):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_step_user_unexpected_exception(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with an unexpected exception."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=Exception("DUMMY"),
    ):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT


async def test_step_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ), patch(
        "homeassistant.components.nina.async_setup_entry",
        return_value=True,
    ):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "NINA"


async def test_step_user_no_selection(hass: HomeAssistant) -> None:
    """Test starting a flow by user with no selection."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):

        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "no_selection"}


async def test_step_user_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow by user but it was already configured."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=DUMMY_DATA
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"


async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data={
            CONF_FILTER_CORONA: DUMMY_DATA[CONF_FILTER_CORONA],
            CONF_MESSAGE_SLOTS: DUMMY_DATA[CONF_MESSAGE_SLOTS],
            CONST_REGION_A_TO_D: DUMMY_DATA[CONST_REGION_A_TO_D],
            CONF_REGIONS: {"095760000000": "Aach"},
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nina.async_setup_entry", return_value=True
    ), patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONST_REGION_A_TO_D: ["072350000000_1"],
                CONST_REGION_E_TO_H: [],
                CONST_REGION_I_TO_L: [],
                CONST_REGION_M_TO_Q: [],
                CONST_REGION_R_TO_U: [],
                CONST_REGION_V_TO_Z: [],
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] is None

        assert dict(config_entry.data) == {
            CONF_FILTER_CORONA: DUMMY_DATA[CONF_FILTER_CORONA],
            CONF_MESSAGE_SLOTS: DUMMY_DATA[CONF_MESSAGE_SLOTS],
            CONST_REGION_A_TO_D: ["072350000000_1"],
            CONST_REGION_E_TO_H: [],
            CONST_REGION_I_TO_L: [],
            CONST_REGION_M_TO_Q: [],
            CONST_REGION_R_TO_U: [],
            CONST_REGION_V_TO_Z: [],
            CONF_REGIONS: {
                "072350000000": "Damflos (Trier-Saarburg - Rheinland-Pfalz)"
            },
        }


async def test_options_flow_with_no_selection(hass: HomeAssistant) -> None:
    """Test config flow options with no selection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=DUMMY_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nina.async_setup_entry", return_value=True
    ), patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONST_REGION_A_TO_D: [],
                CONST_REGION_E_TO_H: [],
                CONST_REGION_I_TO_L: [],
                CONST_REGION_M_TO_Q: [],
                CONST_REGION_R_TO_U: [],
                CONST_REGION_V_TO_Z: [],
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] == {"base": "no_selection"}


async def test_options_flow_connection_error(hass: HomeAssistant) -> None:
    """Test config flow options but no connection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=DUMMY_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=ApiError("Could not connect to Api"),
    ), patch(
        "homeassistant.components.nina.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_unexpected_exception(hass: HomeAssistant) -> None:
    """Test config flow options but with an unexpected exception."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=DUMMY_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=Exception("DUMMY"),
    ), patch(
        "homeassistant.components.nina.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.ABORT


async def test_options_flow_entity_removal(hass: HomeAssistant) -> None:
    """Test if old entities are removed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=DUMMY_DATA,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_MESSAGE_SLOTS: 2,
                CONST_REGION_A_TO_D: ["072350000000", "095760000000"],
                CONST_REGION_E_TO_H: [],
                CONST_REGION_I_TO_L: [],
                CONST_REGION_M_TO_Q: [],
                CONST_REGION_R_TO_U: [],
                CONST_REGION_V_TO_Z: [],
            },
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        entity_registry: er = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )

        assert len(entries) == 2
