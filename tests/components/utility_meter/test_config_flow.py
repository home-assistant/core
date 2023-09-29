"""Test the Utility Meter config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

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


async def test_change_device_source(hass: HomeAssistant) -> None:
    """Test remove the device registry configuration entry when the source entity changes."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Configure source entity 1 (with a linked device)
    source_config_entry_1 = MockConfigEntry()
    source_device_entry_1 = device_registry.async_get_or_create(
        config_entry_id=source_config_entry_1.entry_id,
        identifiers={("sensor", "identifier_test1")},
        connections={("mac", "20:31:32:33:34:35")},
    )
    source_entity_1 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source1",
        config_entry=source_config_entry_1,
        device_id=source_device_entry_1.id,
    )

    # Configure source entity 2 (with a linked device)
    source_config_entry_2 = MockConfigEntry()
    source_device_entry_2 = device_registry.async_get_or_create(
        config_entry_id=source_config_entry_2.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    source_entity_2 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source2",
        config_entry=source_config_entry_2,
        device_id=source_device_entry_2.id,
    )

    # Configure source entity 3 (without a device)
    source_config_entry_3 = MockConfigEntry()
    source_entity_3 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source3",
        config_entry=source_config_entry_3,
    )

    await hass.async_block_till_done()

    input_sensor_entity_id_1 = "sensor.test_source1"
    input_sensor_entity_id_2 = "sensor.test_source2"
    input_sensor_entity_id_3 = "sensor.test_source3"

    # Test the existence of configured source entities
    assert entity_registry.async_get(input_sensor_entity_id_1) is not None
    assert entity_registry.async_get(input_sensor_entity_id_2) is not None
    assert entity_registry.async_get(input_sensor_entity_id_3) is not None

    # Setup the config entry with source entity 1 (with a linked device)
    current_entity_source = source_entity_1
    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": current_entity_source.entity_id,
            "tariffs": [],
        },
        title="Energy",
    )
    utility_meter_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm that the configuration entry has been added to the source entity 1 (current) device registry
    current_device = device_registry.async_get(
        device_id=current_entity_source.device_id
    )
    assert utility_meter_config_entry.entry_id in current_device.config_entries

    # Change configuration options to use source entity 2 (with a linked device) and reload the integration
    previous_entity_source = source_entity_1
    current_entity_source = source_entity_2

    result = await hass.config_entries.options.async_init(
        utility_meter_config_entry.entry_id
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "periodically_resetting": True,
            "source": current_entity_source.entity_id,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Confirm that the configuration entry has been removed from the source entity 1 (previous) device registry
    previous_device = device_registry.async_get(
        device_id=previous_entity_source.device_id
    )
    assert utility_meter_config_entry.entry_id not in previous_device.config_entries

    # Confirm that the configuration entry has been added to the source entity 2 (current) device registry
    current_device = device_registry.async_get(
        device_id=current_entity_source.device_id
    )
    assert utility_meter_config_entry.entry_id in current_device.config_entries

    # Change configuration options to use source entity 3 (without a device) and reload the integration
    previous_entity_source = source_entity_2
    current_entity_source = source_entity_3

    result = await hass.config_entries.options.async_init(
        utility_meter_config_entry.entry_id
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "periodically_resetting": True,
            "source": current_entity_source.entity_id,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Confirm that the configuration entry has been removed from the source entity 2 (previous) device registry
    previous_device = device_registry.async_get(
        device_id=previous_entity_source.device_id
    )
    assert utility_meter_config_entry.entry_id not in previous_device.config_entries

    # Confirm that there is no device with the helper configuration entry
    assert (
        dr.async_entries_for_config_entry(
            device_registry, utility_meter_config_entry.entry_id
        )
        == []
    )

    # Change configuration options to use source entity 2 (with a linked device) and reload the integration
    previous_entity_source = source_entity_3
    current_entity_source = source_entity_2

    result = await hass.config_entries.options.async_init(
        utility_meter_config_entry.entry_id
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "periodically_resetting": True,
            "source": current_entity_source.entity_id,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Confirm that the configuration entry has been added to the source entity 2 (current) device registry
    current_device = device_registry.async_get(
        device_id=current_entity_source.device_id
    )
    assert utility_meter_config_entry.entry_id in current_device.config_entries
