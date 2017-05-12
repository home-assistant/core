"""The tests for the Conversation component."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.setup import setup_component
import homeassistant.components as core_components
from homeassistant.components import conversation
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import get_test_home_assistant, assert_setup_component


class TestConversation(unittest.TestCase):
    """Test the conversation component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.ent_id = 'light.kitchen_lights'
        self.hass = get_test_home_assistant()
        self.hass.states.set(self.ent_id, 'on')
        self.assertTrue(run_coroutine_threadsafe(
            core_components.async_setup(self.hass, {}), self.hass.loop
        ).result())
        with assert_setup_component(0):
            self.assertTrue(setup_component(self.hass, conversation.DOMAIN, {
                conversation.DOMAIN: {}
            }))

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_turn_on(self):
        """Setup and perform good turn on requests."""
        calls = []

        @callback
        def record_call(service):
            """Recorder for a call."""
            calls.append(service)

        self.hass.services.register('light', 'turn_on', record_call)

        event_data = {conversation.ATTR_TEXT: 'turn kitchen lights on'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))

        call = calls[-1]
        self.assertEqual('light', call.domain)
        self.assertEqual('turn_on', call.service)
        self.assertEqual([self.ent_id], call.data[ATTR_ENTITY_ID])

    def test_turn_off(self):
        """Setup and perform good turn off requests."""
        calls = []

        @callback
        def record_call(service):
            """Recorder for a call."""
            calls.append(service)

        self.hass.services.register('light', 'turn_off', record_call)

        event_data = {conversation.ATTR_TEXT: 'turn kitchen lights off'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))

        call = calls[-1]
        self.assertEqual('light', call.domain)
        self.assertEqual('turn_off', call.service)
        self.assertEqual([self.ent_id], call.data[ATTR_ENTITY_ID])

    @patch('homeassistant.components.conversation.logging.Logger.error')
    @patch('homeassistant.core.ServiceRegistry.call')
    def test_bad_request_format(self, mock_logger, mock_call):
        """Setup and perform a badly formatted request."""
        event_data = {
            conversation.ATTR_TEXT:
            'what is the answer to the ultimate question of life, ' +
            'the universe and everything'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))
        self.assertTrue(mock_logger.called)
        self.assertFalse(mock_call.called)

    @patch('homeassistant.components.conversation.logging.Logger.error')
    @patch('homeassistant.core.ServiceRegistry.call')
    def test_bad_request_entity(self, mock_logger, mock_call):
        """Setup and perform requests with bad entity id."""
        event_data = {conversation.ATTR_TEXT: 'turn something off'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))
        self.assertTrue(mock_logger.called)
        self.assertFalse(mock_call.called)

    @patch('homeassistant.components.conversation.logging.Logger.error')
    @patch('homeassistant.core.ServiceRegistry.call')
    def test_bad_request_command(self, mock_logger, mock_call):
        """Setup and perform requests with bad command."""
        event_data = {conversation.ATTR_TEXT: 'turn kitchen lights over'}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))
        self.assertTrue(mock_logger.called)
        self.assertFalse(mock_call.called)

    @patch('homeassistant.components.conversation.logging.Logger.error')
    @patch('homeassistant.core.ServiceRegistry.call')
    def test_bad_request_notext(self, mock_logger, mock_call):
        """Setup and perform requests with bad command with no text."""
        event_data = {}
        self.assertTrue(self.hass.services.call(
            conversation.DOMAIN, 'process', event_data, True))
        self.assertTrue(mock_logger.called)
        self.assertFalse(mock_call.called)
