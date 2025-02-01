"""Test the Integration - Riemann sum integral config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.integration.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.integration.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "method": "left",
                "name": "My integration",
                "round": 1,
                "source": input_sensor_entity_id,
                "unit_time": "min",
                "max_sub_interval": {"seconds": 0},
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My integration"
    assert result["data"] == {}
    assert result["options"] == {
        "method": "left",
        "name": "My integration",
        "round": 1.0,
        "source": "sensor.input",
        "unit_time": "min",
        "max_sub_interval": {"seconds": 0},
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "method": "left",
        "name": "My integration",
        "round": 1.0,
        "source": "sensor.input",
        "unit_time": "min",
        "max_sub_interval": {"seconds": 0},
    }
    assert config_entry.title == "My integration"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise KeyError("Wanted key absent from schema")


@pytest.mark.parametrize("platform", ["sensor"])
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "method": "left",
            "name": "My integration",
            "round": 1.0,
            "source": "sensor.input",
            "unit_prefix": "k",
            "unit_time": "min",
            "max_sub_interval": {"minutes": 1},
        },
        title="My integration",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.input", 10, {"unit_of_measurement": "dog"})
    hass.states.async_set("sensor.valid", 10, {"unit_of_measurement": "dog"})
    hass.states.async_set("sensor.invalid", 10, {"unit_of_measurement": "cat"})

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "round") == 1.0

    source = schema["source"]
    assert isinstance(source, selector.EntitySelector)
    assert source.config["include_entities"] == [
        "sensor.input",
        "sensor.valid",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "method": "right",
            "round": 2.0,
            "source": "sensor.input",
            "max_sub_interval": {"minutes": 1},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "method": "right",
        "name": "My integration",
        "round": 2.0,
        "source": "sensor.input",
        "unit_prefix": "k",
        "unit_time": "min",
        "max_sub_interval": {"minutes": 1},
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "method": "right",
        "name": "My integration",
        "round": 2.0,
        "source": "sensor.input",
        "unit_prefix": "k",
        "unit_time": "min",
        "max_sub_interval": {"minutes": 1},
    }
    assert config_entry.title == "My integration"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 4

    # Check the state of the entity has changed as expected
    hass.states.async_set("sensor.input", 10, {"unit_of_measurement": "dog"})
    hass.states.async_set("sensor.input", 11, {"unit_of_measurement": "dog"})
    await hass.async_block_till_done()

    state = hass.states.get(f"{platform}.my_integration")
    assert state.state != "unknown"
    assert state.attributes["unit_of_measurement"] == "kdogmin"
