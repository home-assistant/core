"""Tests for mcp23017 config flow."""

import copy

from homeassistant import data_entry_flow
import homeassistant.components.mcp23017.binary_sensor as binary_sensor
from homeassistant.components.mcp23017.const import (
    CONF_FLOW_PIN_NAME,
    CONF_FLOW_PIN_NUMBER,
    CONF_FLOW_PLATFORM,
    CONF_I2C_ADDRESS,
    CONF_INVERT_LOGIC,
    CONF_PINS,
    CONF_PULL_MODE,
    DOMAIN,
    MODE_DOWN,
    MODE_UP,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PLATFORM
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_show_config_form(hass):
    """Test Config Flow form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    default_config = result["data_schema"]({})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER

    assert default_config[CONF_I2C_ADDRESS] == 0x20
    assert default_config[CONF_FLOW_PIN_NUMBER] == 0
    assert default_config[CONF_FLOW_PLATFORM] == "binary_sensor"


async def test_create_entry(hass):
    """Test entry creation from config flow.

    Create entry from form inputs.
    """

    await async_setup_component(hass, "persistent_notification", {})

    config = {
        CONF_I2C_ADDRESS: 0x27,
        CONF_FLOW_PIN_NUMBER: 8,
        CONF_FLOW_PLATFORM: "binary_sensor",
    }

    # Patch async_setup_entry to avoid effective component creation
    with patch(
        "homeassistant.components.mcp23017.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=copy.copy(config)
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert "pin_name" in result["data"]
    assert result["data"].pop("pin_name") == "pin 0x%02x:%d" % (
        config[CONF_I2C_ADDRESS],
        config[CONF_FLOW_PIN_NUMBER],
    )
    assert result["data"] == config


async def test_import_entry(hass):
    """Test entry creation from import aka configuration.yaml."""

    await async_setup_component(hass, "persistent_notification", {})

    config = binary_sensor.PLATFORM_SCHEMA(
        {CONF_PLATFORM: DOMAIN, CONF_PINS: {0: "in_0"}}
    )
    config[CONF_FLOW_PIN_NUMBER] = 0
    config[CONF_FLOW_PIN_NAME] = "in_0"

    # Patch async_setup_entry to avoid effective component creation
    with patch(
        "homeassistant.components.mcp23017.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == config


async def test_unique_entry(hass):
    """Test entry creation of a second entry with the same unique id."""

    await async_setup_component(hass, "persistent_notification", {})

    config = {
        CONF_I2C_ADDRESS: 0x27,
        CONF_FLOW_PIN_NUMBER: 8,
        CONF_FLOW_PLATFORM: "binary_sensor",
    }

    initial_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{DOMAIN}.{config[CONF_I2C_ADDRESS]}.{config[CONF_FLOW_PIN_NUMBER]}",
    )
    initial_entry.add_to_hass(hass)

    # Patch async_setup_entry to avoid effective component creation
    with patch(
        "homeassistant.components.mcp23017.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=copy.copy(config)
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_option_flow(hass):
    """Test Config Flow option form and option handling."""

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_FLOW_PLATFORM: "binary_sensor"})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    default_config = result["data_schema"]({})

    assert default_config == {
        CONF_INVERT_LOGIC: False,
        CONF_PULL_MODE: MODE_UP,
    }

    new_config = {
        CONF_INVERT_LOGIC: True,
        CONF_PULL_MODE: MODE_DOWN,
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=copy.copy(new_config)
    )

    assert result["type"] == "create_entry"
    assert result["data"] == new_config
