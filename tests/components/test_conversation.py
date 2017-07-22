"""The tests for the Conversation component."""
# pylint: disable=protected-access
import asyncio
import unittest
from unittest.mock import patch

from homeassistant.core import callback
from homeassistant.setup import setup_component, async_setup_component
import homeassistant.components as core_components
from homeassistant.components import conversation
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.util.async import run_coroutine_threadsafe
from homeassistant.helpers import intent

from tests.common import get_test_home_assistant, async_mock_intent


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


@asyncio.coroutine
def test_calling_intent(hass):
    """Test calling an intent from a conversation."""
    intents = async_mock_intent(hass, 'OrderBeer')

    result = yield from async_setup_component(hass, 'conversation', {
        'conversation': {
            'intents': {
                'OrderBeer': [
                    'I would like the {type} beer'
                ]
            }
        }
    })
    assert result

    yield from hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: 'I would like the Grolsch beer'
        })
    yield from hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'conversation'
    assert intent.intent_type == 'OrderBeer'
    assert intent.slots == {'type': {'value': 'Grolsch'}}
    assert intent.text_input == 'I would like the Grolsch beer'


@asyncio.coroutine
def test_register_before_setup(hass):
    """Test calling an intent from a conversation."""
    intents = async_mock_intent(hass, 'OrderBeer')

    hass.components.conversation.async_register('OrderBeer', [
        'A {type} beer, please'
    ])

    result = yield from async_setup_component(hass, 'conversation', {
        'conversation': {
            'intents': {
                'OrderBeer': [
                    'I would like the {type} beer'
                ]
            }
        }
    })
    assert result

    yield from hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: 'A Grolsch beer, please'
        })
    yield from hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'conversation'
    assert intent.intent_type == 'OrderBeer'
    assert intent.slots == {'type': {'value': 'Grolsch'}}
    assert intent.text_input == 'A Grolsch beer, please'

    yield from hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: 'I would like the Grolsch beer'
        })
    yield from hass.async_block_till_done()

    assert len(intents) == 2
    intent = intents[1]
    assert intent.platform == 'conversation'
    assert intent.intent_type == 'OrderBeer'
    assert intent.slots == {'type': {'value': 'Grolsch'}}
    assert intent.text_input == 'I would like the Grolsch beer'


@asyncio.coroutine
def test_http_processing_intent(hass, test_client):
    """Test processing intent via HTTP API."""
    class TestIntentHandler(intent.IntentHandler):
        intent_type = 'OrderBeer'

        @asyncio.coroutine
        def async_handle(self, intent):
            """Handle the intent."""
            response = intent.create_response()
            response.async_set_speech(
                "I've ordered a {}!".format(intent.slots['type']['value']))
            response.async_set_card(
                "Beer ordered",
                "You chose a {}.".format(intent.slots['type']['value']))
            return response

    intent.async_register(hass, TestIntentHandler())

    result = yield from async_setup_component(hass, 'conversation', {
        'conversation': {
            'intents': {
                'OrderBeer': [
                    'I would like the {type} beer'
                ]
            }
        }
    })
    assert result

    client = yield from test_client(hass.http.app)
    resp = yield from client.post('/api/conversation/process', json={
        'text': 'I would like the Grolsch beer'
    })

    assert resp.status == 200
    data = yield from resp.json()

    assert data == {
        'card': {
            'simple': {
                'content': 'You chose a Grolsch.',
                'title': 'Beer ordered'
            }},
        'speech': {
            'plain': {
                'extra_data': None,
                'speech': "I've ordered a Grolsch!"
            }
        }
    }
