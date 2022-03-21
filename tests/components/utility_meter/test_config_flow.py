"""Test the Utility Meter config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.helpers import entity_registry as er

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
        "homeassistant.components.utility_meter.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "cycle": "monthly",
                "name": "Electricity meter",
                "offset": {"seconds": 0},
                "source": input_sensor_entity_id,
                "tariffs": "",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Electricity meter"
    assert result["data"] == {}
    assert result["options"] == {
        "cycle": "monthly",
        "name": "Electricity meter",
        "offset": {"seconds": 0},
        "source": input_sensor_entity_id,
        "tariffs": "",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "cycle": "monthly",
        "name": "Electricity meter",
        "offset": {"seconds": 0},
        "source": input_sensor_entity_id,
        "tariffs": "",
    }
    assert config_entry.title == "Electricity meter"


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema.keys():
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize(
    "tariffs_1,expected_entities_1,tariffs_2,expected_entities_2",
    (
        (
            "",
            ["sensor.electricity_meter"],
            "high,low",
            [
                "sensor.electricity_meter_low",
                "sensor.electricity_meter_high",
                "select.electricity_meter",
            ],
        ),
        (
            "high,low",
            [
                "sensor.electricity_meter_low",
                "sensor.electricity_meter_high",
                "select.electricity_meter",
            ],
            "",
            ["sensor.electricity_meter"],
        ),
    ),
)
async def test_options(
    hass: HomeAssistant, tariffs_1, expected_entities_1, tariffs_2, expected_entities_2
) -> None:
    """Test reconfiguring."""
    entity_registry = er.async_get(hass)
    input_sensor_entity_id = "sensor.input1"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "name": "Electricity meter",
            "offset": {"seconds": 0},
            "source": input_sensor_entity_id,
            "tariffs": tariffs_1,
        },
        title="Electricity meter",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(expected_entities_1)
    assert len(entity_registry.entities) == len(expected_entities_1)
    for entity in expected_entities_1:
        assert hass.states.get(entity)
        assert entity in entity_registry.entities

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "cycle") == "monthly"
    assert get_suggested(schema, "offset") == {"seconds": 0}
    assert get_suggested(schema, "tariffs") == tariffs_1

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"cycle": "yearly", "offset": {"days": 5}, "tariffs": tariffs_2},
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "cycle": "yearly",
        "name": "Electricity meter",
        "offset": {"days": 5},
        "source": input_sensor_entity_id,
        "tariffs": tariffs_2,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "cycle": "yearly",
        "name": "Electricity meter",
        "offset": {"days": 5},
        "source": input_sensor_entity_id,
        "tariffs": tariffs_2,
    }
    assert config_entry.title == "Electricity meter"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(expected_entities_2)
    assert len(entity_registry.entities) == len(expected_entities_2)
    for entity in expected_entities_2:
        assert hass.states.get(entity)
        assert entity in entity_registry.entities
