"""
tests.components.notify.test_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests notify demo component
"""
import unittest

import homeassistant.core as ha
import homeassistant.components.notify as notify
from homeassistant.components.notify import demo


class TestNotifyDemo(unittest.TestCase):
    """ Test the demo notify. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.assertTrue(notify.setup(self.hass, {
            'notify': {
                'platform': 'demo'
            }
        }))
        self.events = []

        def record_event(event):
            self.events.append(event)

        self.hass.bus.listen(demo.EVENT_NOTIFY, record_event)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_sending_templated_message(self):
        self.hass.states.set('sensor.temperature', 10)
        notify.send_message(self.hass, '{{ states.sensor.temperature.state }}',
                            '{{ states.sensor.temperature.name }}')
        self.hass.pool.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE], 'temperature')
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], '10')
