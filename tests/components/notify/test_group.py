"""The tests for the notify.group platform."""
import unittest
from unittest.mock import MagicMock, patch

from homeassistant.setup import setup_component
import homeassistant.components.notify as notify
from homeassistant.components.notify import group, demo
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import assert_setup_component, get_test_home_assistant


class TestNotifyGroup(unittest.TestCase):
    """Test the notify.group platform."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.events = []
        self.service1 = demo.DemoNotificationService(self.hass)
        self.service2 = demo.DemoNotificationService(self.hass)

        self.service1.send_message = MagicMock(autospec=True)
        self.service2.send_message = MagicMock(autospec=True)

        def mock_get_service(hass, config, discovery_info=None):
            if config['name'] == 'demo1':
                return self.service1
            else:
                return self.service2

        with assert_setup_component(2), \
                patch.object(demo, 'get_service', mock_get_service):
            setup_component(self.hass, notify.DOMAIN, {
                'notify': [{
                    'name': 'demo1',
                    'platform': 'demo'
                }, {
                    'name': 'demo2',
                    'platform': 'demo'
                }]
            })

        self.service = run_coroutine_threadsafe(
            group.async_get_service(self.hass, {'services': [
                {'service': 'demo1'},
                {'service': 'demo2',
                 'data': {'target': 'unnamed device',
                          'data': {'test': 'message'}}}]}),
            self.hass.loop
        ).result()

        assert self.service is not None

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop everything that was started."""
        self.hass.stop()

    def test_send_message_with_data(self):
        """Test sending a message with to a notify group."""
        run_coroutine_threadsafe(
            self.service.async_send_message(
                'Hello', title='Test notification', data={'hello': 'world'}),
            self.hass.loop).result()
        self.hass.block_till_done()

        assert self.service1.send_message.mock_calls[0][1][0] == 'Hello'
        assert self.service1.send_message.mock_calls[0][2] == {
            'title': 'Test notification',
            'data': {'hello': 'world'}
        }
        assert self.service2.send_message.mock_calls[0][1][0] == 'Hello'
        assert self.service2.send_message.mock_calls[0][2] == {
            'target': ['unnamed device'],
            'title': 'Test notification',
            'data': {'hello': 'world', 'test': 'message'}
        }
