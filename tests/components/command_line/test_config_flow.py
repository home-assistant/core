"""The tests for the Command line Config Flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.command_line.const import CONF_COMMAND_TIMEOUT, DOMAIN
from homeassistant.components.command_line.schema import CONF_JSON_ATTRIBUTES
from homeassistant.const import CONF_COMMAND, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    CONFIG_IMPORT_BINARY_SENSOR,
    CONFIG_IMPORT_COVER,
    CONFIG_IMPORT_NOTIFY,
    CONFIG_IMPORT_SENSOR,
    CONFIG_IMPORT_SWITCH,
    ENTRY_CONFIG_SENSOR,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.command_line.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Command Line Test",
                CONF_PLATFORM: "sensor",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "final"

    with patch(
        "homeassistant.components.command_line.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            ENTRY_CONFIG_SENSOR,
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Command Line Test"
    assert result3["options"] == {
        "name": "Command Line Test",
        "platform": "sensor",
        "command": "echo 1",
        "unit_of_measurement": "in",
        "value_template": "{{value | float}}",
        "command_timeout": 15,
        "json_attributes": None,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "config_import,result_dict",
    [
        (
            {**CONFIG_IMPORT_SENSOR, CONF_PLATFORM: "sensor"},
            {
                **CONFIG_IMPORT_SENSOR,
                CONF_PLATFORM: "sensor",
                CONF_JSON_ATTRIBUTES: None,
            },
        ),
        (
            {**CONFIG_IMPORT_BINARY_SENSOR, CONF_PLATFORM: "binary_sensor"},
            {**CONFIG_IMPORT_BINARY_SENSOR, CONF_PLATFORM: "binary_sensor"},
        ),
        (
            {**CONFIG_IMPORT_COVER, CONF_PLATFORM: "cover"},
            {**CONFIG_IMPORT_COVER, CONF_PLATFORM: "cover"},
        ),
        (
            {**CONFIG_IMPORT_SWITCH, CONF_PLATFORM: "switch"},
            {**CONFIG_IMPORT_SWITCH, CONF_PLATFORM: "switch"},
        ),
        (
            {**CONFIG_IMPORT_NOTIFY, CONF_PLATFORM: "notify"},
            {**CONFIG_IMPORT_NOTIFY, CONF_PLATFORM: "notify"},
        ),
    ],
)
async def test_import_flow_success(
    hass: HomeAssistant, config_import: dict[str, Any], result_dict: dict[str, Any]
) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.command_line.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config_import,
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Command Line Test"
    assert result2["options"] == result_dict
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_already_exist(hass: HomeAssistant) -> None:
    """Test import of yaml already exist."""

    MockConfigEntry(domain=DOMAIN, data={}, options=CONFIG_IMPORT_SENSOR).add_to_hass(
        hass
    )

    with patch(
        "homeassistant.components.command_line.async_setup_entry",
        return_value=True,
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONFIG_IMPORT_SENSOR,
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_ABORT
    assert result3["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            **ENTRY_CONFIG_SENSOR,
            CONF_NAME: "Command Line Test",
            CONF_PLATFORM: "sensor",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_state = hass.states.get("sensor.command_line_test")
    assert entity_state
    assert entity_state.state == "1.0"

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            **ENTRY_CONFIG_SENSOR,
            CONF_COMMAND_TIMEOUT: 20,
            CONF_COMMAND: "echo 2",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "platform": "sensor",
        "name": "Command Line Test",
        "command": "echo 2",
        "unit_of_measurement": "in",
        "value_template": "{{value | float}}",
        "command_timeout": 20,
        "json_attributes": None,
    }

    entity_state = hass.states.get("sensor.command_line_test")
    assert entity_state
    assert entity_state.state == "2.0"
