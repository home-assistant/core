"""Test the Min/Max config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, get_schema_suggested_value


@pytest.mark.parametrize("platform", ["sensor"])
async def test_config_flow(hass: HomeAssistant, platform: str) -> None:
    """Test the config flow."""
    input_sensors = ["sensor.input_one", "sensor.input_two"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.min_max.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "My min_max", "entity_ids": input_sensors, "type": "max"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My min_max"
    assert result["data"] == {}
    assert result["options"] == {
        "entity_ids": input_sensors,
        "name": "My min_max",
        "round_digits": 2.0,
        "type": "max",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_ids": input_sensors,
        "name": "My min_max",
        "round_digits": 2.0,
        "type": "max",
    }
    assert config_entry.title == "My min_max"


@pytest.mark.parametrize("platform", ["sensor"])
async def test_options(hass: HomeAssistant, platform: str) -> None:
    """Test reconfiguring."""
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")
    hass.states.async_set("sensor.input_three", "33.33")

    input_sensors1 = ["sensor.input_one", "sensor.input_two"]
    input_sensors2 = ["sensor.input_one", "sensor.input_two", "sensor.input_three"]

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": input_sensors1,
            "name": "My min_max",
            "round_digits": 0,
            "type": "min",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_schema_suggested_value(schema, "entity_ids") == input_sensors1
    assert get_schema_suggested_value(schema, "round_digits") == 0
    assert get_schema_suggested_value(schema, "type") == "min"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "entity_ids": input_sensors2,
            "round_digits": 1,
            "type": "mean",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entity_ids": input_sensors2,
        "name": "My min_max",
        "round_digits": 1,
        "type": "mean",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_ids": input_sensors2,
        "name": "My min_max",
        "round_digits": 1,
        "type": "mean",
    }
    assert config_entry.title == "My min_max"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 4

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_min_max")
    assert state.state == "21.1"
