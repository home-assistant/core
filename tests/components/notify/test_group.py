"""The tests for the notify.group platform."""
import unittest

from homeassistant.bootstrap import setup_component
import homeassistant.components.notify as notify
from homeassistant.components.notify import group

from tests.common import get_test_home_assistant


class TestNotifyGroup(unittest.TestCase):
    """Test the notify.group platform."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.events = []
        self.assertTrue(setup_component(self.hass, notify.DOMAIN, {
            'notify': [{
                'name': 'demo1',
                'platform': 'demo'
            }, {
                'name': 'demo2',
                'platform': 'demo'
            }]
        }))

        self.service = group.get_service(self.hass, {'services': [
            {'service': 'demo1'},
            {'service': 'demo2',
             'data': {'target': 'unnamed device',
                      'data': {'test': 'message'}}}]})

        assert self.service is not None

        def record_event(event):
            """Record event to send notification."""
            self.events.append(event)

        self.hass.bus.listen("notify", record_event)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop everything that was started."""
        self.hass.stop()

    def test_send_message_to_group(self):
        """Test sending a message to a notify group."""
        self.service.send_message('Hello', title='Test notification')
        self.hass.block_till_done()
        self.assertTrue(len(self.events) == 2)
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE],
                         'Test notification')
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], 'Hello')

    def test_send_message_with_data(self):
        """Test sending a message with to a notify group."""
        notify_data = {'hello': 'world'}
        self.service.send_message('Hello', title='Test notification',
                                  data=notify_data)
        self.hass.block_till_done()
        last_event = self.events[-1]
        self.assertEqual(last_event.data[notify.ATTR_TITLE],
                         'Test notification')
        self.assertEqual(last_event.data[notify.ATTR_MESSAGE], 'Hello')
        self.assertEqual(last_event.data[notify.ATTR_DATA], notify_data)

    def test_entity_data_passes_through(self):
        """Test sending a message with data to merge to a notify group."""
        notify_data = {'hello': 'world'}
        self.service.send_message('Hello', title='Test notification',
                                  data=notify_data)
        self.hass.block_till_done()
        data = self.events[-1].data
        assert {
            'message': 'Hello',
            'target': 'unnamed device',
            'title': 'Test notification',
            'data': {'hello': 'world', 'test': 'message'}
        } == data
