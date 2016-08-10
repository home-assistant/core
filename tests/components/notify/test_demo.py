"""The tests for the notify demo platform."""
import tempfile
import unittest

import homeassistant.components.notify as notify
from homeassistant.components.notify import demo
from homeassistant.helpers import script
from homeassistant.util import yaml

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

    def test_sending_none_message(self):
        """Test send with None as message."""
        notify.send_message(self.hass, None)
        self.hass.pool.block_till_done()
        self.assertTrue(len(self.events) == 0)

    def test_sending_templated_message(self):
        """Send a templated message."""
        self.hass.states.set('sensor.temperature', 10)
        notify.send_message(self.hass, '{{ states.sensor.temperature.state }}',
                            '{{ states.sensor.temperature.name }}')
        self.hass.pool.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE], 'temperature')
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], '10')

    def test_method_forwards_correct_data(self):
        """Test that all data from the service gets forwarded to service."""
        notify.send_message(self.hass, 'my message', 'my title',
                            {'hello': 'world'})
        self.hass.pool.block_till_done()
        self.assertTrue(len(self.events) == 1)
        data = self.events[0].data
        assert {
            'message': 'my message',
            'target': None,
            'title': 'my title',
            'data': {'hello': 'world'}
        } == data

    def test_calling_notify_from_script_loaded_from_yaml(self):
        """Test if we can call a notify from a script."""
        yaml_conf = """
service: notify.notify
data:
  data:
    push:
      sound: US-EN-Morgan-Freeman-Roommate-Is-Arriving.wav
data_template:
  message: >
          Test 123 {{ 2 + 2 }}
"""

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(yaml_conf.encode('utf-8'))
            fp.flush()
            conf = yaml.load_yaml(fp.name)

        script.call_from_config(self.hass, conf)
        self.hass.pool.block_till_done()
        self.assertTrue(len(self.events) == 1)
        assert {
            'message': 'Test 123 4',
            'target': None,
            'title': 'Home Assistant',
            'data': {
                'push': {
                    'sound':
                    'US-EN-Morgan-Freeman-Roommate-Is-Arriving.wav'}}
        } == self.events[0].data
