"""Test the Nina config flow."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
from unittest.mock import patch

from pynina import ApiError

from homeassistant.components.nina.const import (
    CONF_AREA_FILTER,
    CONF_FILTERS,
    CONF_HEADLINE_FILTER,
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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from . import mocked_request_function

from tests.common import MockConfigEntry, load_fixture

DUMMY_DATA: dict[str, Any] = {
    CONF_MESSAGE_SLOTS: 5,
    CONST_REGION_A_TO_D: ["095760000000_0", "095760000000_1"],
    CONST_REGION_E_TO_H: ["160650000000_14", "146260000000_0"],
    CONST_REGION_I_TO_L: ["083370000000_22", "055660000000_5"],
    CONST_REGION_M_TO_Q: ["010590000000_25", "032510000000_40"],
    CONST_REGION_R_TO_U: ["010560000000_16", "010590000000_94"],
    CONST_REGION_V_TO_Z: ["010610000000_73", "010610000000_74"],
    CONF_FILTERS: {
        CONF_HEADLINE_FILTER: ".*corona.*",
        CONF_AREA_FILTER: ".*",
    },
}

DUMMY_RESPONSE_REGIONS: dict[str, Any] = json.loads(
    load_fixture("sample_regions.json", "nina")
)
DUMMY_RESPONSE_WARNIGNS: dict[str, Any] = json.loads(
    load_fixture("sample_warnings.json", "nina")
)

OPTIONS_ENTRY_DATA: dict[str, Any] = {
    CONF_FILTERS: deepcopy(DUMMY_DATA[CONF_FILTERS]),
    CONF_MESSAGE_SLOTS: deepcopy(DUMMY_DATA[CONF_MESSAGE_SLOTS]),
    CONST_REGION_A_TO_D: deepcopy(DUMMY_DATA[CONST_REGION_A_TO_D]),
    CONF_REGIONS: {"095760000000": "Aach"},
}


async def test_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test starting a flow by user but no connection."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=ApiError("Could not connect to Api"),
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_fetch"


async def test_step_user_unexpected_exception(hass: HomeAssistant) -> None:
    """Test starting a flow by user but with an unexpected exception."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        side_effect=Exception("DUMMY"),
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_step_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with (
        patch(
            "pynina.baseApi.BaseAPI._makeRequest",
            wraps=mocked_request_function,
        ),
        patch(
            "homeassistant.components.nina.async_setup_entry",
            return_value=True,
        ),
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "NINA"
        assert result["data"] == DUMMY_DATA | {
            CONF_REGIONS: {
                "095760000000": "Allersberg, M (Roth - Bayern) + Büchenbach (Roth - Bayern)"
            }
        }
        assert result["version"] == 1
        assert result["minor_version"] == 3


async def test_step_user_no_selection(hass: HomeAssistant) -> None:
    """Test starting a flow by user with no selection."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_FILTERS: {CONF_HEADLINE_FILTER: ""}},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "no_selection"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=deepcopy(DUMMY_DATA),
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "NINA"
        assert result["data"] == DUMMY_DATA | {
            CONF_REGIONS: {
                "095760000000": "Allersberg, M (Roth - Bayern) + Büchenbach (Roth - Bayern)"
            }
        }


async def test_step_user_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow by user but it was already configured."""
    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"


async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=deepcopy(OPTIONS_ENTRY_DATA),
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nina.async_setup_entry", return_value=True),
        patch(
            "pynina.baseApi.BaseAPI._makeRequest",
            wraps=mocked_request_function,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
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
                CONF_FILTERS: {
                    CONF_HEADLINE_FILTER: ".*corona.*",
                    CONF_AREA_FILTER: ".*",
                },
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}

        assert dict(config_entry.data) == {
            CONF_FILTERS: DUMMY_DATA[CONF_FILTERS],
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
        data=deepcopy(OPTIONS_ENTRY_DATA),
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.nina.async_setup_entry", return_value=True),
        patch(
            "pynina.baseApi.BaseAPI._makeRequest",
            wraps=mocked_request_function,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.FORM
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
                CONF_FILTERS: {CONF_HEADLINE_FILTER: ""},
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "init"
        assert result["errors"] == {"base": "no_selection"}

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONST_REGION_A_TO_D: ["095760000000_0"],
                CONST_REGION_E_TO_H: [],
                CONST_REGION_I_TO_L: [],
                CONST_REGION_M_TO_Q: [],
                CONST_REGION_R_TO_U: [],
                CONST_REGION_V_TO_Z: [],
                CONF_FILTERS: {
                    CONF_HEADLINE_FILTER: ".*corona.*",
                    CONF_AREA_FILTER: ".*",
                },
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {}

        assert dict(config_entry.data) == {
            CONF_FILTERS: DUMMY_DATA[CONF_FILTERS],
            CONF_MESSAGE_SLOTS: DUMMY_DATA[CONF_MESSAGE_SLOTS],
            CONST_REGION_A_TO_D: ["095760000000_0"],
            CONST_REGION_E_TO_H: [],
            CONST_REGION_I_TO_L: [],
            CONST_REGION_M_TO_Q: [],
            CONST_REGION_R_TO_U: [],
            CONST_REGION_V_TO_Z: [],
            CONF_REGIONS: {"095760000000": "Allersberg, M (Roth - Bayern)"},
        }


async def test_options_flow_connection_error(hass: HomeAssistant) -> None:
    """Test config flow options but no connection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=deepcopy(OPTIONS_ENTRY_DATA),
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "pynina.baseApi.BaseAPI._makeRequest",
            side_effect=ApiError("Could not connect to Api"),
        ),
        patch(
            "homeassistant.components.nina.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_fetch"


async def test_options_flow_unexpected_exception(hass: HomeAssistant) -> None:
    """Test config flow options but with an unexpected exception."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=deepcopy(OPTIONS_ENTRY_DATA),
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "pynina.baseApi.BaseAPI._makeRequest",
            side_effect=Exception("DUMMY"),
        ),
        patch(
            "homeassistant.components.nina.async_setup_entry",
            return_value=True,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unknown"


async def test_options_flow_entity_removal(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test if old entities are removed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=deepcopy(OPTIONS_ENTRY_DATA) | {CONF_REGIONS: {"095760000000": "Aach"}},
        version=1,
        minor_version=3,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "pynina.baseApi.BaseAPI._makeRequest",
            wraps=mocked_request_function,
        ),
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
                CONF_FILTERS: {},
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY

        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )

        assert len(entries) == 2
