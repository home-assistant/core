"""Test the Derivative config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.derivative.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector

from tests.common import MockConfigEntry, get_schema_suggested_value


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
        "homeassistant.components.derivative.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My derivative",
                "round": 1,
                "source": input_sensor_entity_id,
                "time_window": {"seconds": 0},
                "unit_time": "min",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My derivative"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My derivative",
        "round": 1.0,
        "source": "sensor.input",
        "time_window": {"seconds": 0.0},
        "unit_time": "min",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My derivative",
        "round": 1.0,
        "source": "sensor.input",
        "time_window": {"seconds": 0.0},
        "unit_time": "min",
    }
    assert config_entry.title == "My derivative"


@pytest.mark.parametrize("platform", ["sensor"])
async def test_options(hass: HomeAssistant, platform) -> None:
    """Test reconfiguring."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.input",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
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
    assert get_schema_suggested_value(schema, "round") == 1.0
    assert get_schema_suggested_value(schema, "time_window") == {"seconds": 0.0}
    assert get_schema_suggested_value(schema, "unit_prefix") == "k"
    assert get_schema_suggested_value(schema, "unit_time") == "min"

    source = schema["source"]
    assert isinstance(source, selector.EntitySelector)
    assert source.config["include_entities"] == [
        "sensor.input",
        "sensor.valid",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "source": "sensor.valid",
            "round": 2.0,
            "time_window": {"seconds": 10.0},
            "unit_time": "h",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My derivative",
        "round": 2.0,
        "source": "sensor.valid",
        "time_window": {"seconds": 10.0},
        "unit_time": "h",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My derivative",
        "round": 2.0,
        "source": "sensor.valid",
        "time_window": {"seconds": 10.0},
        "unit_time": "h",
    }
    assert config_entry.title == "My derivative"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 4

    # Check the state of the entity has changed as expected
    hass.states.async_set("sensor.valid", 10, {"unit_of_measurement": "cat"})
    hass.states.async_set("sensor.valid", 11, {"unit_of_measurement": "cat"})
    await hass.async_block_till_done()
    state = hass.states.get(f"{platform}.my_derivative")
    assert state.attributes["unit_of_measurement"] == "cat/h"
