"""Test the Nina config flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

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

from . import setup_platform
from .const import DUMMY_USER_INPUT

from tests.common import MockConfigEntry


def assert_dummy_entry_created(result: dict[str, Any]) -> None:
    """Asserts that an entry from DUMMY_USER_INPUT is created."""
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NINA"
    assert result["data"] == DUMMY_USER_INPUT | {
        CONF_REGIONS: {
            "095760000000": "Allersberg, M (Roth - Bayern) + Büchenbach (Roth - Bayern)"
        }
    }
    assert result["version"] == 1
    assert result["minor_version"] == 3


async def test_step_user_connection_error(
    hass: HomeAssistant, mock_nina_class: AsyncMock
) -> None:
    """Test starting a flow by user but no connection."""
    mock_nina_class.get_all_regional_codes.side_effect = ApiError(
        "Could not connect to Api"
    )

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_fetch"


async def test_step_user_unexpected_exception(
    hass: HomeAssistant, mock_nina_class: AsyncMock
) -> None:
    """Test starting a flow by user but with an unexpected exception."""
    mock_nina_class.get_all_regional_codes.side_effect = Exception("DUMMY")

    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_step_user(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_nina_class: AsyncMock
) -> None:
    """Test starting a flow by user with valid values."""
    result: dict[str, Any] = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=deepcopy(DUMMY_USER_INPUT),
    )

    assert_dummy_entry_created(result)


async def test_step_user_no_selection(
    hass: HomeAssistant, mock_nina_class: AsyncMock
) -> None:
    """Test starting a flow by user with no selection."""
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
        user_input=deepcopy(DUMMY_USER_INPUT),
    )

    assert_dummy_entry_created(result)


async def test_step_user_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nina_class: AsyncMock
) -> None:
    """Test starting a flow by user, but it was already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_init(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test config flow options."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

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

    assert dict(mock_config_entry.data) == {
        CONF_FILTERS: DUMMY_USER_INPUT[CONF_FILTERS],
        CONF_MESSAGE_SLOTS: DUMMY_USER_INPUT[CONF_MESSAGE_SLOTS],
        CONST_REGION_A_TO_D: ["072350000000_1"],
        CONST_REGION_E_TO_H: [],
        CONST_REGION_I_TO_L: [],
        CONST_REGION_M_TO_Q: [],
        CONST_REGION_R_TO_U: [],
        CONST_REGION_V_TO_Z: [],
        CONF_REGIONS: {"072350000000": "Damflos (Trier-Saarburg - Rheinland-Pfalz)"},
    }


async def test_options_flow_with_no_selection(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test config flow options with no selection."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

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

    assert dict(mock_config_entry.data) == {
        CONF_FILTERS: DUMMY_USER_INPUT[CONF_FILTERS],
        CONF_MESSAGE_SLOTS: DUMMY_USER_INPUT[CONF_MESSAGE_SLOTS],
        CONST_REGION_A_TO_D: ["095760000000_0"],
        CONST_REGION_E_TO_H: [],
        CONST_REGION_I_TO_L: [],
        CONST_REGION_M_TO_Q: [],
        CONST_REGION_R_TO_U: [],
        CONST_REGION_V_TO_Z: [],
        CONF_REGIONS: {"095760000000": "Allersberg, M (Roth - Bayern)"},
    }


async def test_options_flow_connection_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test config flow options but no connection."""
    mock_nina_class.get_all_regional_codes.side_effect = ApiError(
        "Could not connect to Api"
    )

    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_fetch"


async def test_options_flow_unexpected_exception(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test config flow options but with an unexpected exception."""
    mock_nina_class.get_all_regional_codes.side_effect = Exception("DUMMY")

    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_options_flow_entity_removal(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nina_class: AsyncMock,
    nina_warnings: list[Warning],
) -> None:
    """Test if old entities are removed."""
    await setup_platform(hass, mock_config_entry, mock_nina_class, nina_warnings)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    new_slot_count = 2

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_MESSAGE_SLOTS: new_slot_count,
            CONST_REGION_A_TO_D: ["095760000000"],
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
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entries) == new_slot_count
