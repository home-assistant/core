"""Test setting up sensors."""
from unittest.mock import AsyncMock, patch

from iotawattpy.sensor import Sensor
import pytest

from homeassistant.components.iotawatt.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DEVICE_CLASS_ENERGY,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_iotawatt():
    """Mock iotawatt."""
    with patch("homeassistant.components.iotawatt.Iotawatt") as mock:
        instance = mock.return_value
        instance.update = AsyncMock()
        instance.getSensors.return_value = {"sensors": {}}
        yield instance


async def test_sensors(hass, mock_iotawatt):
    """Test sensors work."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = Sensor(
        channel="1",
        name="My Sensor",
        io_type="Input",
        unit="WattHours",
        value="23",
        begin="",
        mac_addr="mock-mac",
    )
    MockConfigEntry(
        domain=DOMAIN, data={"name": "Test", "host": "1.2.3.4"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get("sensor.iotawatt_input_my_sensor")
    assert state is not None
    assert state.state == "23"
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_TOTAL_INCREASING
    assert state.attributes[ATTR_FRIENDLY_NAME] == "IoTaWatt Input My Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ENERGY
    assert state.attributes["channel"] == "1"
    assert state.attributes["type"] == "Input"


async def test_sensor_units(hass, mock_iotawatt):
    """Tests the different types of units."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_watt_sensor_key"] = Sensor(
        channel="1",
        name="My Watt Sensor",
        io_type="Input",
        unit="Watts",
        value="23",
        begin="",
        mac_addr="mock-mac",
    )
    mock_iotawatt.getSensors.return_value["sensors"]["my_volt_sensor_key"] = Sensor(
        channel="2",
        name="My Volt Sensor",
        io_type="Input",
        unit="Volts",
        value="118",
        begin="",
        mac_addr="mock-mac",
    )
    mock_iotawatt.getSensors.return_value["sensors"]["my_pf_sensor_key"] = Sensor(
        channel="3",
        name="My PF Sensor",
        io_type="Output",
        unit="PF",
        value="0.95",
        begin="",
        mac_addr="mock-mac",
    )
    MockConfigEntry(
        domain=DOMAIN, data={"name": "Test", "host": "1.2.3.4"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 3

    state = hass.states.get("sensor.iotawatt_input_my_watt_sensor")
    assert state is not None
    assert state.state == "23"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "IoTaWatt Input My Watt Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == POWER_WATT
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_POWER
    assert state.attributes["channel"] == "1"
    assert state.attributes["type"] == "Input"

    state = hass.states.get("sensor.iotawatt_input_my_volt_sensor")
    assert state is not None
    assert state.state == "118"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "IoTaWatt Input My Volt Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ELECTRIC_POTENTIAL_VOLT
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_VOLTAGE
    assert state.attributes["channel"] == "2"
    assert state.attributes["type"] == "Input"

    state = hass.states.get("sensor.iotawatt_output_my_pf_sensor")
    assert state is not None
    assert state.state == "0.95"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "IoTaWatt Output My PF Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "PF"
    assert state.attributes["type"] == "Output"
