"""The tests for the Command line Config Flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.command_line.const import CONF_COMMAND_TIMEOUT, DOMAIN
from homeassistant.const import CONF_COMMAND, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from . import ENTRY_CONFIG_SENSOR

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
