"""The tests for the PG LAB Electronics cover."""
import json

from homeassistant.components import cover
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient

COVER_SUPPORT = (
    cover.CoverEntityFeature.OPEN
    | cover.CoverEntityFeature.CLOSE
    | cover.CoverEntityFeature.STOP
)


async def call_service(hass: HomeAssistant, entity_id, service, **kwargs):
    """Call a service."""
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {"entity_id": entity_id, **kwargs},
        blocking=True,
    )


async def test_cover_support(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Test cover support."""
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
        "params": {"shutters": 4, "boards": "10000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all("cover")) == 4

    state = hass.states.get("cover.test_shutter0")
    assert state.attributes["supported_features"] == COVER_SUPPORT

    state = hass.states.get("cover.test_shutter1")
    assert state.attributes["supported_features"] == COVER_SUPPORT

    state = hass.states.get("cover.test_shutter2")
    assert state.attributes["supported_features"] == COVER_SUPPORT

    state = hass.states.get("cover.test_shutter3")
    assert state.attributes["supported_features"] == COVER_SUPPORT


async def test_available_cover(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Check if shutter are properly created."""
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
        "params": {"shutters": 5, "boards": "11000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    for i in range(4):
        state = hass.states.get(f"cover.test_shutter{i}")
        assert state.state == STATE_UNKNOWN
        assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_change_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Test state update via MQTT."""
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
        "params": {"shutters": 2, "boards": "10000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # Simulate response from the device
    state = hass.states.get("cover.test_shutter0")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Cover OPEN
    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "OPEN")
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_shutter0")
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.state == STATE_OPEN

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "OPENING")
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_shutter0")
    assert state.state == STATE_OPENING

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "CLOSING")
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_shutter0")
    assert state.state == STATE_CLOSING

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "CLOSED")
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_shutter0")
    assert state.state == STATE_CLOSED


async def test_mqtt_state_by_calling_service(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Calling service to OPEN/CLOSE cover and check mqtt state."""
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
        "params": {"shutters": 2, "boards": "10000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.test_shutter0")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Open the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_shutter0", SERVICE_OPEN_COVER)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/shutter/0/set", "OPEN", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Stop the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_shutter0", SERVICE_STOP_COVER)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/shutter/0/set", "STOP", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Close the cover and verify MQTT message is sent
    await call_service(hass, "cover.test_shutter0", SERVICE_CLOSE_COVER)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/shutter/0/set", "CLOSE", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
