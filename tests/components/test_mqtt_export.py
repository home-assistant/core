"""The tests for the MQTT export component."""
import unittest
from unittest.mock import patch

import homeassistant.components.mqtt_export as export
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant,
    mock_mqtt_component,
    fire_time_changed
)


class TestMqttExport(unittest.TestCase):
    """Test the MQTT export module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        super(TestMqttExport, self).setUp()
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def add_export(self, pub_topic=None):
        """Add a mqtt_export component to hass."""
        config = {}
        if pub_topic:
            config['publish_topic'] = pub_topic
        return export.setup(self.hass, {export.DOMAIN: config})

    def test_setup_succeeds(self):
        """Test if setup is successful."""
        self.assertTrue(self.add_export())

    @patch('homeassistant.components.mqtt.publish')
    def test_time_event_does_not_send_message(self, mock_pub):
        """"Test of not sending a new message if time event."""
        self.assertTrue(self.add_export(pub_topic='bar'))
        self.hass.pool.block_till_done()
        mock_pub.reset_mock()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.assertFalse(mock_pub.called)
