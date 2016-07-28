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

        self.hass.bus.listen(demo.EVENT_NOTIFY_MESSAGE, record_event)
        self.hass.bus.listen(demo.EVENT_NOTIFY_PHOTO, record_event)
        self.hass.bus.listen(demo.EVENT_NOTIFY_LOCATION, record_event)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop down everything that was started."""
        self.hass.stop()

    def test_sending_none_message(self):
        """Test send with None as message."""
        notify.send_message(self.hass, None)
        self.hass.pool.block_till_done()
        self.assertTrue(len(self.events) == 0)

    def test_sending_templated_message(self):
        """Send a templated message."""
        self.hass.states.set('sensor.temperature', 10)
        notify.send_message(self.hass,
                            message='{{ states.sensor.temperature.state }}',
                            title='{{ states.sensor.temperature.name }}')
        self.hass.pool.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE], 'temperature')
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], '10')

    def test_sending_photo(self):
        """Send a photo."""
        notify.send_photo(self.hass, file="/tmp/test.png", caption="test")
        self.hass.pool.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_CAPTION], 'test')
        self.assertEqual(last_event.data[notify.ATTR_PHOTO][notify.ATTR_FILE],
                         '/tmp/test.png')

    def test_sending_location(self):
        """Send a location."""
        notify.send_location(self.hass, latitude=7.83, longitude=46.23,
                             caption="test")
        self.hass.pool.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_LATITUDE], 7.83)
        self.assertEqual(last_event.data[notify.ATTR_LONGITUDE], 46.23)
        self.assertEqual(last_event.data[notify.ATTR_CAPTION], 'test')
