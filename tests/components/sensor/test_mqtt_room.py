"""The tests for the MQTT room presence sensor."""
import json
import datetime
import unittest
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
import homeassistant.components.sensor as sensor
from homeassistant.components.mqtt import (CONF_STATE_TOPIC, CONF_QOS,
                                           DEFAULT_QOS)
from homeassistant.const import (CONF_NAME, CONF_PLATFORM)
from homeassistant.util import dt

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)

DEVICE_ID = '123TESTMAC'
NAME = 'test_device'
BEDROOM = 'bedroom'
LIVING_ROOM = 'living_room'

BEDROOM_TOPIC = "room_presence/{}".format(BEDROOM)
LIVING_ROOM_TOPIC = "room_presence/{}".format(LIVING_ROOM)

SENSOR_STATE = "sensor.{}".format(NAME)

CONF_DEVICE_ID = 'device_id'
CONF_TIMEOUT = 'timeout'

NEAR_MESSAGE = {
    'id': DEVICE_ID,
    'name': NAME,
    'distance': 1
}

FAR_MESSAGE = {
    'id': DEVICE_ID,
    'name': NAME,
    'distance': 10
}

REALLY_FAR_MESSAGE = {
    'id': DEVICE_ID,
    'name': NAME,
    'distance': 20
}


class TestMQTTRoomSensor(unittest.TestCase):
    """Test the room presence sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.assertTrue(setup_component(self.hass, sensor.DOMAIN, {
            sensor.DOMAIN: {
                CONF_PLATFORM: 'mqtt_room',
                CONF_NAME: NAME,
                CONF_DEVICE_ID: DEVICE_ID,
                CONF_STATE_TOPIC: 'room_presence',
                CONF_QOS: DEFAULT_QOS,
                CONF_TIMEOUT: 5
            }}))

        # Clear state between tests
        self.hass.states.set(SENSOR_STATE, None)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def send_message(self, topic, message):
        """Test the sending of a message."""
        fire_mqtt_message(
            self.hass, topic, json.dumps(message))
        self.hass.block_till_done()

    def assert_state(self, room):
        """Test the assertion of a room state."""
        state = self.hass.states.get(SENSOR_STATE)
        self.assertEqual(state.state, room)

    def assert_distance(self, distance):
        """Test the assertion of a distance state."""
        state = self.hass.states.get(SENSOR_STATE)
        self.assertEqual(state.attributes.get('distance'), distance)

    def test_room_update(self):
        """Test the updating between rooms."""
        self.send_message(BEDROOM_TOPIC, FAR_MESSAGE)
        self.assert_state(BEDROOM)
        self.assert_distance(10)

        self.send_message(LIVING_ROOM_TOPIC, NEAR_MESSAGE)
        self.assert_state(LIVING_ROOM)
        self.assert_distance(1)

        self.send_message(BEDROOM_TOPIC, FAR_MESSAGE)
        self.assert_state(LIVING_ROOM)
        self.assert_distance(1)

        time = dt.utcnow() + datetime.timedelta(seconds=7)
        with patch('homeassistant.helpers.condition.dt_util.utcnow',
                   return_value=time):
            self.send_message(BEDROOM_TOPIC, FAR_MESSAGE)
            self.assert_state(BEDROOM)
            self.assert_distance(10)
