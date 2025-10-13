"""Test the Generic Cover config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.generic_cover.const import (
    CONF_DURATION,
    CONF_SWITCH_CLOSE,
    CONF_SWITCH_OPEN,
    CONF_TILT_DURATION,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.generic_cover.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Cover",
                CONF_SWITCH_OPEN: "switch.test_open",
                CONF_SWITCH_CLOSE: "switch.test_close",
                CONF_DURATION: {
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 10,
                    "milliseconds": 0,
                },
                CONF_TILT_DURATION: {
                    "hours": 0,
                    "minutes": 0,
                    "seconds": 2,
                    "milliseconds": 0,
                },
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Cover"
    assert result2["data"] == {
        CONF_NAME: "Test Cover",
        CONF_SWITCH_OPEN: "switch.test_open",
        CONF_SWITCH_CLOSE: "switch.test_close",
        CONF_DURATION: {"hours": 0, "minutes": 0, "seconds": 10, "milliseconds": 0},
        CONF_TILT_DURATION: {"hours": 0, "minutes": 0, "seconds": 2, "milliseconds": 0},
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_duration(hass: HomeAssistant) -> None:
    """Test we handle invalid duration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Cover",
            CONF_SWITCH_OPEN: "switch.test_open",
            CONF_SWITCH_CLOSE: "switch.test_close",
            CONF_DURATION: {"hours": 0, "minutes": 0, "seconds": 0, "milliseconds": 0},
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_DURATION: "invalid_duration"}


async def test_form_invalid_tilt_duration(hass: HomeAssistant) -> None:
    """Test we handle invalid tilt duration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Cover",
            CONF_SWITCH_OPEN: "switch.test_open",
            CONF_SWITCH_CLOSE: "switch.test_close",
            CONF_TILT_DURATION: {
                "hours": 0,
                "minutes": 0,
                "seconds": 0,
                "milliseconds": 0,
            },
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_TILT_DURATION: "invalid_tilt_duration"}


async def test_form_same_switch(hass: HomeAssistant) -> None:
    """Test we handle same switch for open and close."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Cover",
            CONF_SWITCH_OPEN: "switch.test_switch",
            CONF_SWITCH_CLOSE: "switch.test_switch",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "same_switch"}


async def test_form_duplicate_entry(hass: HomeAssistant) -> None:
    """Test we handle duplicate entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Cover",
        data={
            CONF_NAME: "Test Cover",
            CONF_SWITCH_OPEN: "switch.test_open",
            CONF_SWITCH_CLOSE: "switch.test_close",
        },
        unique_id="switch.test_open_switch.test_close",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Cover",
            CONF_SWITCH_OPEN: "switch.test_open",
            CONF_SWITCH_CLOSE: "switch.test_close",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.generic_cover.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SWITCH_OPEN: "switch.test_open_new",
            CONF_SWITCH_CLOSE: "switch.test_close_new",
            CONF_DURATION: {"hours": 0, "minutes": 0, "seconds": 15, "milliseconds": 0},
            CONF_TILT_DURATION: {
                "hours": 0,
                "minutes": 0,
                "seconds": 3,
                "milliseconds": 0,
            },
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_SWITCH_OPEN: "switch.test_open_new",
        CONF_SWITCH_CLOSE: "switch.test_close_new",
        CONF_DURATION: {"hours": 0, "minutes": 0, "seconds": 15, "milliseconds": 0},
        CONF_TILT_DURATION: {"hours": 0, "minutes": 0, "seconds": 3, "milliseconds": 0},
    }
