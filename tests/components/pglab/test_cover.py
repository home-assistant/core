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

COVER_FEATURES = (
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


async def test_cover_features(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Test cover features."""
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

    for i in range(4):
        cover = hass.states.get(f"cover.test_shutter_{i}")
        assert cover
        assert cover.attributes["supported_features"] == COVER_FEATURES


async def test_cover_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_pglab
) -> None:
    """Check if covers are properly created."""
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
        "params": {"shutters": 6, "boards": "11000000"},
    }

    async_fire_mqtt_message(
        hass,
        topic,
        json.dumps(payload),
    )
    await hass.async_block_till_done()

    # We are creating 6 covers using two E-RELAY devices connected to E-BOARD.
    # Now we are going to check if all covers are created and their state is unknown.
    for i in range(5):
        cover = hass.states.get(f"cover.test_shutter_{i}")
        assert cover.state == STATE_UNKNOWN
        assert not cover.attributes.get(ATTR_ASSUMED_STATE)

    # The cover with id 7 should not be created.
    cover = hass.states.get("cover.test_shutter_7")
    assert not cover


async def test_cover_change_state_via_mqtt(
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

    # Check initial state is unknown
    cover = hass.states.get("cover.test_shutter_0")
    assert cover.state == STATE_UNKNOWN
    assert not cover.attributes.get(ATTR_ASSUMED_STATE)

    # Simulate the device responds sending mqtt messages and check if the cover state
    # change appropriately.

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "OPEN")
    await hass.async_block_till_done()
    cover = hass.states.get("cover.test_shutter_0")
    assert not cover.attributes.get(ATTR_ASSUMED_STATE)
    assert cover.state == STATE_OPEN

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "OPENING")
    await hass.async_block_till_done()
    cover = hass.states.get("cover.test_shutter_0")
    assert cover.state == STATE_OPENING

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "CLOSING")
    await hass.async_block_till_done()
    cover = hass.states.get("cover.test_shutter_0")
    assert cover.state == STATE_CLOSING

    async_fire_mqtt_message(hass, "pglab/test/shutter/0/state", "CLOSED")
    await hass.async_block_till_done()
    cover = hass.states.get("cover.test_shutter_0")
    assert cover.state == STATE_CLOSED


async def test_cover_mqtt_state_by_calling_service(
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

    cover = hass.states.get("cover.test_shutter_0")
    assert cover.state == STATE_UNKNOWN
    assert not cover.attributes.get(ATTR_ASSUMED_STATE)

    # Call HA covers services and verify that the MQTT messages are sent correctly

    await call_service(hass, "cover.test_shutter_0", SERVICE_OPEN_COVER)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/shutter/0/set", "OPEN", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await call_service(hass, "cover.test_shutter_0", SERVICE_STOP_COVER)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/shutter/0/set", "STOP", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await call_service(hass, "cover.test_shutter_0", SERVICE_CLOSE_COVER)
    mqtt_mock.async_publish.assert_called_once_with(
        "pglab/test/shutter/0/set", "CLOSE", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
