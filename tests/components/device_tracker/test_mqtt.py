"""The tests for the MQTT device tracker platform."""
import asyncio
import unittest
from unittest.mock import patch
import logging
import os

from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.const import CONF_PLATFORM

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)

_LOGGER = logging.getLogger(__name__)


class TestComponentsDeviceTrackerMQTT(unittest.TestCase):
    """Test MQTT device tracker platform."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_ensure_device_tracker_platform_validation(self): \
            # pylint: disable=invalid-name
        """Test if platform validation was done."""
        @asyncio.coroutine
        def mock_setup_scanner(hass, config, see, discovery_info=None):
            """Check that Qos was added by validation."""
            self.assertTrue('qos' in config)

        with patch('homeassistant.components.device_tracker.mqtt.'
                   'async_setup_scanner', autospec=True,
                   side_effect=mock_setup_scanner) as mock_sp:

            dev_id = 'paulus'
            topic = '/location/paulus'
            assert setup_component(self.hass, device_tracker.DOMAIN, {
                device_tracker.DOMAIN: {
                    CONF_PLATFORM: 'mqtt',
                    'devices': {dev_id: topic}
                }
            })
            assert mock_sp.call_count == 1

    def test_new_message(self):
        """Test new message."""
        dev_id = 'paulus'
        enttiy_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
        topic = '/location/paulus'
        location = 'work'

        self.hass.config.components = set(['mqtt', 'zone'])
        assert setup_component(self.hass, device_tracker.DOMAIN, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                'devices': {dev_id: topic}
            }
        })
        fire_mqtt_message(self.hass, topic, location)
        self.hass.block_till_done()
        self.assertEqual(location, self.hass.states.get(enttiy_id).state)
