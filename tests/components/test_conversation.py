"""The tests for the Conversation component."""
# pylint: disable=protected-access
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import conversation
import homeassistant.components as component
from homeassistant.components.cover import (SERVICE_OPEN_COVER)
from homeassistant.helpers import intent

from tests.common import async_mock_intent, async_mock_service


async def test_calling_intent(hass):
    """Test calling an intent from a conversation."""
    intents = async_mock_intent(hass, 'OrderBeer')

    result = await component.async_setup(hass, {})
    assert result

    result = await async_setup_component(hass, 'conversation', {
        'conversation': {
            'intents': {
                'OrderBeer': [
                    'I would like the {type} beer'
                ]
            }
        }
    })
    assert result

    await hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: 'I would like the Grolsch beer'
        })
    await hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'conversation'
    assert intent.intent_type == 'OrderBeer'
    assert intent.slots == {'type': {'value': 'Grolsch'}}
    assert intent.text_input == 'I would like the Grolsch beer'


async def test_register_before_setup(hass):
    """Test calling an intent from a conversation."""
    intents = async_mock_intent(hass, 'OrderBeer')

    hass.components.conversation.async_register('OrderBeer', [
        'A {type} beer, please'
    ])

    result = await async_setup_component(hass, 'conversation', {
        'conversation': {
            'intents': {
                'OrderBeer': [
                    'I would like the {type} beer'
                ]
            }
        }
    })
    assert result

    await hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: 'A Grolsch beer, please'
        })
    await hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == 'conversation'
    assert intent.intent_type == 'OrderBeer'
    assert intent.slots == {'type': {'value': 'Grolsch'}}
    assert intent.text_input == 'A Grolsch beer, please'

    await hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: 'I would like the Grolsch beer'
        })
    await hass.async_block_till_done()

    assert len(intents) == 2
    intent = intents[1]
    assert intent.platform == 'conversation'
    assert intent.intent_type == 'OrderBeer'
    assert intent.slots == {'type': {'value': 'Grolsch'}}
    assert intent.text_input == 'I would like the Grolsch beer'


async def test_http_processing_intent(hass, test_client):
    """Test processing intent via HTTP API."""
    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = 'OrderBeer'

        async def async_handle(self, intent):
            """Handle the intent."""
            response = intent.create_response()
            response.async_set_speech(
                "I've ordered a {}!".format(intent.slots['type']['value']))
            response.async_set_card(
                "Beer ordered",
                "You chose a {}.".format(intent.slots['type']['value']))
            return response

    intent.async_register(hass, TestIntentHandler())

    result = await async_setup_component(hass, 'conversation', {
        'conversation': {
            'intents': {
                'OrderBeer': [
                    'I would like the {type} beer'
                ]
            }
        }
    })
    assert result

    client = await test_client(hass.http.app)
    resp = await client.post('/api/conversation/process', json={
        'text': 'I would like the Grolsch beer'
    })

    assert resp.status == 200
    data = await resp.json()

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


@pytest.mark.parametrize('sentence', ('turn on kitchen', 'turn kitchen on'))
async def test_turn_on_intent(hass, sentence):
    """Test calling the turn on intent."""
    result = await component.async_setup(hass, {})
    assert result

    result = await async_setup_component(hass, 'conversation', {})
    assert result

    hass.states.async_set('light.kitchen', 'off')
    calls = async_mock_service(hass, 'homeassistant', 'turn_on')

    await hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: sentence
        })
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'homeassistant'
    assert call.service == 'turn_on'
    assert call.data == {'entity_id': 'light.kitchen'}


async def test_cover_intents_loading(hass):
    """Test Cover Intents Loading."""
    with pytest.raises(intent.UnknownIntent):
        await intent.async_handle(
            hass, 'test', 'HassOpenCover', {'name': {'value': 'garage door'}}
        )

    result = await async_setup_component(hass, 'cover', {})
    assert result

    hass.states.async_set('cover.garage_door', 'closed')
    calls = async_mock_service(hass, 'cover', SERVICE_OPEN_COVER)

    response = await intent.async_handle(
        hass, 'test', 'HassOpenCover', {'name': {'value': 'garage door'}}
    )
    await hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Opened garage door'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'cover'
    assert call.service == 'open_cover'
    assert call.data == {'entity_id': 'cover.garage_door'}


@pytest.mark.parametrize('sentence', ('turn off kitchen', 'turn kitchen off'))
async def test_turn_off_intent(hass, sentence):
    """Test calling the turn on intent."""
    result = await component.async_setup(hass, {})
    assert result

    result = await async_setup_component(hass, 'conversation', {})
    assert result

    hass.states.async_set('light.kitchen', 'on')
    calls = async_mock_service(hass, 'homeassistant', 'turn_off')

    await hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: sentence
        })
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'homeassistant'
    assert call.service == 'turn_off'
    assert call.data == {'entity_id': 'light.kitchen'}


@pytest.mark.parametrize('sentence', ('toggle kitchen', 'kitchen toggle'))
async def test_toggle_intent(hass, sentence):
    """Test calling the turn on intent."""
    result = await component.async_setup(hass, {})
    assert result

    result = await async_setup_component(hass, 'conversation', {})
    assert result

    hass.states.async_set('light.kitchen', 'on')
    calls = async_mock_service(hass, 'homeassistant', 'toggle')

    await hass.services.async_call(
        'conversation', 'process', {
            conversation.ATTR_TEXT: sentence
        })
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'homeassistant'
    assert call.service == 'toggle'
    assert call.data == {'entity_id': 'light.kitchen'}


async def test_http_api(hass, test_client):
    """Test the HTTP conversation API."""
    result = await component.async_setup(hass, {})
    assert result

    result = await async_setup_component(hass, 'conversation', {})
    assert result

    client = await test_client(hass.http.app)
    hass.states.async_set('light.kitchen', 'off')
    calls = async_mock_service(hass, 'homeassistant', 'turn_on')

    resp = await client.post('/api/conversation/process', json={
        'text': 'Turn the kitchen on'
    })
    assert resp.status == 200

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'homeassistant'
    assert call.service == 'turn_on'
    assert call.data == {'entity_id': 'light.kitchen'}


async def test_http_api_wrong_data(hass, test_client):
    """Test the HTTP conversation API."""
    result = await component.async_setup(hass, {})
    assert result

    result = await async_setup_component(hass, 'conversation', {})
    assert result

    client = await test_client(hass.http.app)

    resp = await client.post('/api/conversation/process', json={
        'text': 123
    })
    assert resp.status == 400

    resp = await client.post('/api/conversation/process', json={
    })
    assert resp.status == 400


def test_create_matcher():
    """Test the create matcher method."""
    # Basic sentence
    pattern = conversation._create_matcher('Hello world')
    assert pattern.match('Hello world') is not None

    # Match a part
    pattern = conversation._create_matcher('Hello {name}')
    match = pattern.match('hello world')
    assert match is not None
    assert match.groupdict()['name'] == 'world'
    no_match = pattern.match('Hello world, how are you?')
    assert no_match is None

    # Optional and matching part
    pattern = conversation._create_matcher('Turn on [the] {name}')
    match = pattern.match('turn on the kitchen lights')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen lights'
    match = pattern.match('turn on kitchen lights')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen lights'
    match = pattern.match('turn off kitchen lights')
    assert match is None

    # Two different optional parts, 1 matching part
    pattern = conversation._create_matcher('Turn on [the] [a] {name}')
    match = pattern.match('turn on the kitchen lights')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen lights'
    match = pattern.match('turn on kitchen lights')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen lights'
    match = pattern.match('turn on a kitchen light')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen light'

    # Strip plural
    pattern = conversation._create_matcher('Turn {name}[s] on')
    match = pattern.match('turn kitchen lights on')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen light'

    # Optional 2 words
    pattern = conversation._create_matcher('Turn [the great] {name} on')
    match = pattern.match('turn the great kitchen lights on')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen lights'
    match = pattern.match('turn kitchen lights on')
    assert match is not None
    assert match.groupdict()['name'] == 'kitchen lights'
