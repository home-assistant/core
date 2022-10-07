"""Test the Attribute as Sensor config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.attribute_as_sensor.const import DOMAIN
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.unit_conversion import TemperatureConverter

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_config_flow(hass: HomeAssistant, platform) -> None:
    """Test the config flow."""
    input_sensor = "sensor.input_one"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.attribute_as_sensor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My attribute_as_sensor",
                "entity_id": input_sensor,
                "icon": "mdi:test-icon",
            },
        )

        await hass.async_block_till_done()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "attr"
        assert result["errors"] is None
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "attribute": "test_attribute",
                "device_class": "speed",
                "state_class": "measurement",
                "unit_of_measurement": "m/s",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My attribute_as_sensor"
    assert result2["data"] == {}
    assert result2["options"] == {
        "entity_id": input_sensor,
        "name": "My attribute_as_sensor",
        "icon": "mdi:test-icon",
        "attribute": "test_attribute",
        "device_class": "speed",
        "state_class": "measurement",
        "unit_of_measurement": "m/s",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor,
        "name": "My attribute_as_sensor",
        "icon": "mdi:test-icon",
        "attribute": "test_attribute",
        "device_class": "speed",
        "state_class": "measurement",
        "unit_of_measurement": "m/s",
    }
    assert config_entry.title == "My attribute_as_sensor"


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
    hass.states.async_set("sensor.input_one", "10", attributes={"test_attribute": 20})

    input_sensor = "sensor.input_one"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor,
            "name": "My attribute_as_sensor",
            "icon": "mdi:test-icon",
            "attribute": "test_attribute",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°C",
        },
        title="My attribute_as_sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°F",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "entity_id": input_sensor,
        "name": "My attribute_as_sensor",
        "icon": "mdi:test-icon",
        "attribute": "test_attribute",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°F",
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "entity_id": input_sensor,
        "name": "My attribute_as_sensor",
        "icon": "mdi:test-icon",
        "attribute": "test_attribute",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°F",
    }
    assert config_entry.title == "My attribute_as_sensor"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 2

    # Check the state of the entity has changed as expected
    state = hass.states.get(f"{platform}.my_attribute_as_sensor")
    metric_state = TemperatureConverter.convert(20, TEMP_FAHRENHEIT, TEMP_CELSIUS)
    assert state.state == str(round(metric_state))
    assert state.attributes["entity_id"] == "sensor.input_one"
