"""The tests for the notify demo platform."""
import unittest

import homeassistant.components.notify as notify
from homeassistant.components.notify import demo

from tests.common import get_test_home_assistant


class TestNotifyDemo(unittest.TestCase):
    """Test the demo notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(notify.setup(self.hass, {
            'notify': {
                'platform': 'demo'
            }
        }))
        self.events = []

        def record_event(event):
            """Record event to send notification."""
            self.events.append(event)

        self.hass.bus.listen(demo.EVENT_NOTIFY, record_event)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop down everything that was started."""
        self.hass.stop()

    def test_sending_templated_message(self):
        """Send a templated message."""
        self.hass.states.set('sensor.temperature', 10)
        notify.send_message(self.hass, '{{ states.sensor.temperature.state }}',
                            '{{ states.sensor.temperature.name }}')
        self.hass.pool.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE], 'temperature')
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], '10')
