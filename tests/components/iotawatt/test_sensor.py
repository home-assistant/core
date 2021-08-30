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
    ENERGY_WATT_HOUR,
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


async def test_sensor_type_output(hass, mock_iotawatt):
    """Tests the sensor type of Output."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_watthour_sensor_key"] = Sensor(
        channel="N/A",
        name="My WattHour Sensor",
        io_type="Output",
        unit="WattHours",
        value="243",
        begin="",
        mac_addr="mock-mac",
    )
    MockConfigEntry(
        domain=DOMAIN, data={"name": "Test", "host": "1.2.3.4"}
    ).add_to_hass(hass)
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get("sensor.iotawatt_output_my_watthour_sensor")
    assert state is not None
    assert state.state == "243"
    assert state.attributes[ATTR_FRIENDLY_NAME] == "IoTaWatt Output My WattHour Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == ENERGY_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ENERGY
    assert state.attributes["type"] == "Output"
