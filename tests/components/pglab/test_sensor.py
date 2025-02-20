"""The tests for the PG LAB Electronics sensor."""

import datetime as dt
import json

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_attributes(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Check if sensor are properly created."""
    topic = "pglab/discovery/E-Board-DD53AC85/config"
    payload = {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": "test",
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-Board",
        "id": "E-Board-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": 0, "boards": "00000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_temperature")
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == UnitOfTemperature.CELSIUS

    state = hass.states.get("sensor.test_mpu_voltage")
    assert state.attributes.get("device_class") == SensorDeviceClass.VOLTAGE
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == UnitOfElectricPotential.VOLT

    state = hass.states.get("sensor.test_run_time")
    assert state.attributes.get("device_class") == SensorDeviceClass.TIMESTAMP
    assert state.attributes.get("icon") == "mdi:progress-clock"


async def test_attributes_update_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Check if sensor are properly created."""
    topic = "pglab/discovery/E-Board-DD53AC85/config"
    payload = {
        "ip": "192.168.1.16",
        "mac": "80:34:28:1B:18:5A",
        "name": "test",
        "hw": "1.0.7",
        "fw": "1.0.0",
        "type": "E-Board",
        "id": "E-Board-DD53AC85",
        "manufacturer": "PG LAB Electronics",
        "params": {"shutters": 0, "boards": "00000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # check original sensors state
    state = hass.states.get("sensor.test_temperature")
    assert state.state == "0"

    state = hass.states.get("sensor.test_mpu_voltage")
    assert state.state == "0"

    # update sensor value via mqtt
    update_payload = {"temp": 33.4, "volt": 3.31, "rtime": 1000}
    async_fire_mqtt_message(hass, "pglab/test/sensor/value", json.dumps(update_payload))
    await hass.async_block_till_done()

    # check new value
    state = hass.states.get("sensor.test_temperature")
    assert state.state == "33.4"

    state = hass.states.get("sensor.test_mpu_voltage")
    assert state.state == "3.31"

    # check the the reboot time sensor, it should be 1000 second before current time
    # be sure that the current time sensor state  is in a valid raange
    state = hass.states.get("sensor.test_run_time")
    assert state.state > (dt.datetime.min).isoformat()
    assert state.state <= (utcnow() - dt.timedelta(seconds=1000)).isoformat()
