import unittest
from threading import Event

from homeassistant.bootstrap import setup_component
from homeassistant.components import telegram_poll
from homeassistant.components.telegram_poll import IncomingChecker, \
    EVENT_TELEGRAM_COMMAND

# pylint: disable=invalid-name
from tests.common import get_test_home_assistant


class TestTelegramPoll(unittest.TestCase):
    """Test the sun module."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mockbot = MockTelegramBot()
        self.checker = IncomingChecker(self.mockbot, self.hass,
                                       [123, 456])

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_1(self):
        def listener():
            return "abc"

        self.hass.bus.listen(EVENT_TELEGRAM_COMMAND, listener)

        self.mockbot.send_message({'text'})
        # setup_component(self.hass, sun.DOMAIN, {
        #     sun.DOMAIN: {sun.CONF_ELEVATION: 0}})


class MockTelegramBot():
    def __init__(self):
        self.update_event = Event()
        self.update_event.clear()
        self.message = {}

    def getUpdates(self, offset=None, limit=100, timeout=0, network_delay=5.,
                   **kwargs):
        self.update_event.wait()
        self.update_event.clear()
        return self.message

    def send_message(self, message):
        self.message = message
        self.update_event.set()
