"""Test the Integration - Riemann sum integral config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.integration.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.integration.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "custom_unit_enable": False,
                "method": "left",
                "name": "My integration",
                "round": 1,
                "source": input_sensor_entity_id,
                "unit": "",
                "unit_prefix": "none",
                "unit_time": "min",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "My integration"
    assert result["data"] == {}
    assert result["options"] == {
        "custom_unit_enable": False,
        "method": "left",
        "name": "My integration",
        "round": 1.0,
        "source": "sensor.input",
        "unit": "",
        "unit_prefix": "none",
        "unit_time": "min",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "custom_unit_enable": False,
        "method": "left",
        "name": "My integration",
        "round": 1.0,
        "source": "sensor.input",
        "unit": "",
        "unit_prefix": "none",
        "unit_time": "min",
    }
    assert config_entry.title == "My integration"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize("platform", ("sensor",))
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "custom_unit_enable": False,
            "method": "left",
            "name": "My integration",
            "round": 1.0,
            "source": "sensor.input",
            "unit": "",
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My integration",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "custom_unit_enable") is False
    assert get_suggested(schema, "method") == "left"
    assert get_suggested(schema, "round") == 1.0
    assert get_suggested(schema, "unit") == ""
    assert get_suggested(schema, "unit_prefix") == "k"
    assert get_suggested(schema, "unit_time") == "min"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "custom_unit_enable": True,
            "method": "right",
            "round": 2.0,
            "unit": "Mcats/h",
            "unit_prefix": "none",
            "unit_time": "h",
        },
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "custom_unit_enable": True,
        "method": "right",
        "name": "My integration",
        "round": 2.0,
        "source": "sensor.input",
        "unit": "Mcats/h",
        "unit_prefix": "none",
        "unit_time": "h",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "custom_unit_enable": True,
        "method": "right",
        "name": "My integration",
        "round": 2.0,
        "source": "sensor.input",
        "unit": "Mcats/h",
        "unit_prefix": "none",
        "unit_time": "h",
    }
    assert config_entry.title == "My integration"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_integration")
    assert state.state == "unknown"
    assert state.attributes["unit_of_measurement"] == "Mcats/h"
