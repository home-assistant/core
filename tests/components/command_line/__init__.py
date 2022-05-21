"""Tests for command_line component."""

from typing import Any

from homeassistant import setup
from homeassistant.components.command_line.const import CONF_COMMAND_TIMEOUT, DOMAIN
from homeassistant.components.command_line.schema import CONF_JSON_ATTRIBUTES
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import (
    CONF_COMMAND,
    CONF_COMMAND_CLOSE,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_COMMAND_OPEN,
    CONF_COMMAND_STATE,
    CONF_COMMAND_STOP,
    CONF_DEVICE_CLASS,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_PAYLOAD_OFF,
    CONF_PAYLOAD_ON,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_test_entity(
    hass: HomeAssistant, domain: str, config_dict: dict[str, Any]
) -> None:
    """Set up a test command line binary_sensor entity."""
    assert await setup.async_setup_component(
        hass,
        domain,
        {domain: {"platform": "command_line", "name": "Test", **config_dict}},
    )
    await hass.async_block_till_done()


async def setup_test_entity_entry(
    hass: HomeAssistant, config_dict: dict[str, Any], source: str = SOURCE_USER
) -> ConfigEntry:
    """Set up a test command line binary_sensor entity."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data={},
        options=config_dict,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


ENTRY_CONFIG_SENSOR = {
    CONF_COMMAND: "echo 1",
    CONF_UNIT_OF_MEASUREMENT: "in",
    CONF_VALUE_TEMPLATE: "{{value | float}}",
    CONF_COMMAND_TIMEOUT: 15,
    CONF_JSON_ATTRIBUTES: [""],
}
CONFIG_IMPORT_SENSOR = {
    CONF_NAME: "Command Line Test",
    CONF_COMMAND: "echo 1",
    CONF_UNIT_OF_MEASUREMENT: "in",
    CONF_VALUE_TEMPLATE: "{{value | float}}",
    CONF_COMMAND_TIMEOUT: 15,
    CONF_JSON_ATTRIBUTES: [],
    CONF_UNIQUE_ID: "unique_id_cmd_sensor",
    CONF_SCAN_INTERVAL: 60,
}
CONFIG_IMPORT_BINARY_SENSOR = {
    CONF_NAME: "Command Line Test",
    CONF_COMMAND: "echo ON",
    CONF_DEVICE_CLASS: "motion",
    CONF_PAYLOAD_ON: "ON",
    CONF_PAYLOAD_OFF: "OFF",
    CONF_VALUE_TEMPLATE: "{{ value }} ",
    CONF_SCAN_INTERVAL: 60,
    CONF_COMMAND_TIMEOUT: 15,
    CONF_UNIQUE_ID: "unique_id_cmd_binary_sensor",
}
CONFIG_IMPORT_COVER = {
    CONF_NAME: "Command Line Test",
    CONF_COMMAND_OPEN: "echo OPEN",
    CONF_COMMAND_CLOSE: "echo CLOSE",
    CONF_COMMAND_STOP: "echo STOP",
    CONF_COMMAND_STATE: "echo OPEN",
    CONF_VALUE_TEMPLATE: "{{ value }} ",
    CONF_COMMAND_TIMEOUT: 15,
    CONF_UNIQUE_ID: "unique_id_cmd_cover",
}
CONFIG_IMPORT_SWITCH = {
    CONF_NAME: "Command Line Test",
    CONF_COMMAND_ON: "echo ON",
    CONF_COMMAND_OFF: "echo OFF",
    CONF_COMMAND_STATE: "echo ON",
    CONF_VALUE_TEMPLATE: "{{ value }}",
    CONF_ICON_TEMPLATE: "{% if value == 'ON' %} mdi:toggle-switch {% else %} mdi:toggle-switch-off {% endif %}",
    CONF_COMMAND_TIMEOUT: 15,
    CONF_UNIQUE_ID: "unique_id_cmd_cover",
}
CONFIG_IMPORT_NOTIFY = {
    CONF_NAME: "Command Line Test",
    CONF_COMMAND: "echo 1",
    CONF_COMMAND_TIMEOUT: 15,
}
