"""Test the Utility Meter config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
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
                "offset": 0,
                "source": input_sensor_entity_id,
                "tariffs": [],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electricity meter"
    assert result["data"] == {}
    assert result["options"] == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": True,
        "source": input_sensor_entity_id,
        "tariffs": [],
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": True,
        "source": input_sensor_entity_id,
        "tariffs": [],
    }
    assert config_entry.title == "Electricity meter"


async def test_tariffs(hass: HomeAssistant) -> None:
    """Test tariffs."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "cycle": "monthly",
            "name": "Electricity meter",
            "offset": 0,
            "source": input_sensor_entity_id,
            "tariffs": ["cat", "dog", "horse", "cow"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electricity meter"
    assert result["data"] == {}
    assert result["options"] == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "periodically_resetting": True,
        "offset": 0,
        "source": input_sensor_entity_id,
        "tariffs": ["cat", "dog", "horse", "cow"],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": True,
        "source": input_sensor_entity_id,
        "tariffs": ["cat", "dog", "horse", "cow"],
    }
    assert config_entry.title == "Electricity meter"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "cycle": "monthly",
            "name": "Electricity meter",
            "offset": 0,
            "source": input_sensor_entity_id,
            "tariffs": ["cat", "cat", "cat", "cat"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "tariffs_not_unique"


async def test_non_periodically_resetting(hass: HomeAssistant) -> None:
    """Test periodically resetting."""
    input_sensor_entity_id = "sensor.input"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "cycle": "monthly",
            "name": "Electricity meter",
            "offset": 0,
            "periodically_resetting": False,
            "source": input_sensor_entity_id,
            "tariffs": [],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electricity meter"
    assert result["data"] == {}
    assert result["options"] == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "periodically_resetting": False,
        "offset": 0,
        "source": input_sensor_entity_id,
        "tariffs": [],
    }

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": False,
        "source": input_sensor_entity_id,
        "tariffs": [],
    }


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


async def test_options(hass: HomeAssistant) -> None:
    """Test reconfiguring."""
    input_sensor1_entity_id = "sensor.input1"
    input_sensor2_entity_id = "sensor.input2"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Electricity meter",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": input_sensor1_entity_id,
            "tariffs": "",
        },
        title="Electricity meter",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert get_suggested(schema, "source") == input_sensor1_entity_id
    assert get_suggested(schema, "periodically_resetting") is True

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"source": input_sensor2_entity_id, "periodically_resetting": False},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": False,
        "source": input_sensor2_entity_id,
        "tariffs": "",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "cycle": "monthly",
        "delta_values": False,
        "name": "Electricity meter",
        "net_consumption": False,
        "offset": 0,
        "periodically_resetting": False,
        "source": input_sensor2_entity_id,
        "tariffs": "",
    }
    assert config_entry.title == "Electricity meter"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    state = hass.states.get("sensor.electricity_meter")
    assert state.attributes["source"] == input_sensor2_entity_id
