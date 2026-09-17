"""Tests for the Entur config flow."""

from typing import Any

from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_SHOW_ON_MAP,
    CONF_STOP_ID,
    CONF_STOP_IDS,
    CONF_WHITELIST_LINES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test configuring Entur from the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STOP_ID: "NSR:StopPlace:548"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Entur"
    assert result["data"] == {
        CONF_NAME: "Entur",
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: True,
        CONF_SHOW_ON_MAP: False,
        CONF_WHITELIST_LINES: [],
        CONF_OMIT_NON_BOARDING: True,
        CONF_NUMBER_OF_DEPARTURES: 2,
    }


async def test_user_flow_rejects_invalid_stop_id(hass: HomeAssistant) -> None:
    """Test that the UI rejects values that are not Entur stop IDs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STOP_ID: "Central station"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_stop_id"}


async def test_user_flow_rejects_incomplete_stop_id(hass: HomeAssistant) -> None:
    """Test that the UI rejects an incomplete Entur stop ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_STOP_ID: "NSR:StopPlace:"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_stop_id"}


async def test_import_flow(hass: HomeAssistant) -> None:
    """Test importing an existing YAML platform configuration."""
    import_data: dict[str, Any] = {
        "platform": DOMAIN,
        CONF_NAME: "Transport",
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: False,
        CONF_SHOW_ON_MAP: True,
        CONF_WHITELIST_LINES: ["RUT:Line:1"],
        CONF_OMIT_NON_BOARDING: False,
        CONF_NUMBER_OF_DEPARTURES: 4,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Transport"
    assert result["data"] == {
        CONF_NAME: "Transport",
        CONF_STOP_IDS: ["NSR:StopPlace:548"],
        CONF_EXPAND_PLATFORMS: False,
        CONF_SHOW_ON_MAP: True,
        CONF_WHITELIST_LINES: ["RUT:Line:1"],
        CONF_OMIT_NON_BOARDING: False,
        CONF_NUMBER_OF_DEPARTURES: 4,
    }
