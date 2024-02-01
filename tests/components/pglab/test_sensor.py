"""The tests for the PG LAB Electronics sensor."""
import json

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def call_service(hass: HomeAssistant, entity_id, service, **kwargs):
    """Call a service."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {"entity_id": entity_id, **kwargs},
        blocking=True,
    )


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

    state = hass.states.get("sensor.test_temp")
    assert state.attributes.get("device_class") == "temperature"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "°C"

    state = hass.states.get("sensor.test_volt")
    assert state.attributes.get("device_class") == "voltage"
    assert state.attributes.get("icon") is None
    assert state.attributes.get("unit_of_measurement") == "V"


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
    state = hass.states.get("sensor.test_temp")
    assert state.state == "0"

    state = hass.states.get("sensor.test_volt")
    assert state.state == "0"

    # update sensor value via mqtt
    update_payload = {"temp": 33.4, "volt": 3.31}
    async_fire_mqtt_message(hass, "pglab/test/sensor/value", json.dumps(update_payload))
    await hass.async_block_till_done()

    # check new value
    state = hass.states.get("sensor.test_temp")
    assert state.state == "33.4"

    state = hass.states.get("sensor.test_volt")
    assert state.state == "3.31"
