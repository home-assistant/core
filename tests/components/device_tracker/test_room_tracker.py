"""The tests for the room presence device tracker."""
import json
import os
import time
import unittest

from homeassistant.components import device_tracker
from homeassistant.const import (STATE_HOME, CONF_PLATFORM)

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)

DEVICE = '123TESTMAC'
NAME = 'test_device'
BEDROOM = 'bedroom'
LIVING_ROOM = 'living_room'

BEDROOM_TOPIC = "room_presence/{}".format(BEDROOM)
LIVING_ROOM_TOPIC = "room_presence/{}".format(LIVING_ROOM)

DEVICE_TRACKER_STATE = "device_tracker.{}".format(NAME)

CONF_TOPIC = 'topic'
CONF_TIMEOUT = 'timeout'

NEAR_MESSAGE = {
    'id': DEVICE,
    'name': NAME,
    'distance': 1
}

FAR_MESSAGE = {
    'id': DEVICE,
    'name': NAME,
    'distance': 10
}

REALLY_FAR_MESSAGE = {
    'id': DEVICE,
    'name': NAME,
    'distance': 20
}


class TestDeviceTrackerRoomPresence(unittest.TestCase):
    """Test the room presence sensor."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)
        self.assertTrue(device_tracker.setup(self.hass, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'room_tracker',
                CONF_TOPIC: 'room_presence',
                CONF_TIMEOUT: 5
            }}))

        # Clear state between tests
        self.hass.states.set(DEVICE_TRACKER_STATE, None)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def send_message(self, topic, message):
        """Test the sending of a message."""
        fire_mqtt_message(
            self.hass, topic, json.dumps(message))
        self.hass.pool.block_till_done()

    def assert_location_state(self, location):
        """Test the assertion of a location state."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.state, location)

    def assert_room_name(self, room_name):
        """Test the assertion of a location latitude."""
        state = self.hass.states.get(DEVICE_TRACKER_STATE)
        self.assertEqual(state.attributes.get('room_name'), room_name)

    def test_room_update(self):
        """Test the updating between rooms."""
        self.send_message(BEDROOM_TOPIC, FAR_MESSAGE)
        self.assert_location_state(STATE_HOME)
        self.assert_room_name(BEDROOM)

        self.send_message(LIVING_ROOM_TOPIC, NEAR_MESSAGE)
        self.assert_location_state(STATE_HOME)
        self.assert_room_name(LIVING_ROOM)

        self.send_message(BEDROOM_TOPIC, FAR_MESSAGE)
        self.assert_room_name(LIVING_ROOM)

        time.sleep(7)
        self.send_message(BEDROOM_TOPIC, FAR_MESSAGE)
        self.assert_room_name(BEDROOM)
