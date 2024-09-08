"""Tests for the weheat sensor platform."""

from random import randint
from unittest.mock import Mock

from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.weheat.const import DOMAIN, SENSOR_DHW_KEY
from homeassistant.components.weheat.sensor import (
    WeheatHeatPumpSensor,
    WeHeatSensorEntityDescription,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_native_value(hass: HomeAssistant, mock_coordinator) -> None:
    """Test the native value of the return the property specified by value_fn."""
    EXPECTED_VALUE = 1.2
    entity = WeHeatSensorEntityDescription(
        translation_key="translation_key",
        key="key_key",
        value_fn=lambda status: status.my_property,
    )
    mock_coordinator.data.my_property = EXPECTED_VALUE
    sensor = WeheatHeatPumpSensor(mock_coordinator, entity)

    actual_value = sensor.native_value

    assert actual_value == EXPECTED_VALUE


async def test_sensor_creation_no_dhw(hass: HomeAssistant, mock_coordinator) -> None:
    """Test the sensors do not include DHW related sensors when the heat pump does not have DHW."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.runtime_data = [mock_coordinator]
    callback = Mock()
    await async_setup_entry(hass, config_entry, callback)

    assert len(callback.mock_calls) == 1
    assert all(
        SENSOR_DHW_KEY not in entity.entity_description.key
        for entity in callback.mock_calls[0].args[0]
    )


async def test_sensor_creation_with_dhw(hass: HomeAssistant, mock_coordinator) -> None:
    """Test the sensors include DHW related sensors when the heat pump has DHW."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    mock_coordinator.heat_pump_info.has_dhw = True
    config_entry.runtime_data = [mock_coordinator]
    callback = Mock()
    await async_setup_entry(hass, config_entry, callback)

    assert len(callback.mock_calls) == 1
    assert any(
        SENSOR_DHW_KEY in entity.entity_description.key
        for entity in callback.mock_calls[0].args[0]
    )


def get_expected_heat_pump_attr(entity: WeheatHeatPumpSensor) -> str:
    """Return the expected heat pump data attribute that the sensor should access.

    This is identical to the sensor key in most cases, expect for the two handled here.
    """
    # for readability the dict has been structured where the key is the heat pump attribute and the value the sensor key
    sensor_keys = {
        "water_house_in_temperature": "ch_inlet_temperature",
        "air_inlet_temperature": "outside_temperature",
    }

    # set the default, which is identical to the sensor key
    data_attr_name = entity.entity_description.key

    # check if this is an exception
    if entity.entity_description.key in sensor_keys.values():
        # Now get the key from the value
        data_attr_name = list(sensor_keys.keys())[
            list(sensor_keys.values()).index(entity.entity_description.key)
        ]

    return data_attr_name


async def test_sensor_value_mapping(hass: HomeAssistant, mock_coordinator) -> None:
    """Test that the sensor value_fn point to the correct attribute int he heat pump data."""
    # Create the entities for 1 heat pump
    config_entry = MockConfigEntry(domain=DOMAIN)
    mock_coordinator.heat_pump_info.has_dhw = True
    config_entry.runtime_data = [mock_coordinator]
    callback = Mock()
    await async_setup_entry(hass, config_entry, callback)
    assert len(callback.mock_calls) == 1

    # for each created sensor check that the native_value property returns the correct data
    for entity in callback.mock_calls[0].args[0]:
        data_attr_name = get_expected_heat_pump_attr(entity)

        # most properties can work with a random number
        return_value = randint(0, 1000)
        expected_value = return_value

        # except for the heat pump state, which is an enum
        if data_attr_name == "heat_pump_state":
            return_value = HeatPump.State.DHW
            expected_value = return_value.name.lower()

        # set the heat pump data to the return value
        setattr(
            mock_coordinator.data,
            data_attr_name,
            return_value,
        )

        # and check if that value is returned
        assert (
            entity.native_value == expected_value
        ), f"Failed for {entity.entity_description.key}"
