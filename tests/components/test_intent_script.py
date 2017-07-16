"""Test intent_script component."""
import asyncio

from homeassistant.bootstrap import async_setup_component
from homeassistant.helpers import intent

from tests.common import async_mock_service


@asyncio.coroutine
def test_intent_script(hass):
    """Test intent scripts work."""
    calls = async_mock_service(hass, 'test', 'service')

    yield from async_setup_component(hass, 'intent_script', {
        'intent_script': {
            'HelloWorld': {
                'action': {
                    'service': 'test.service',
                    'data_template': {
                        'hello': '{{ name }}'
                    }
                },
                'card': {
                    'title': 'Hello {{ name }}',
                    'content': 'Content for {{ name }}',
                },
                'speech': {
                    'text': 'Good morning {{ name }}'
                }
            }
        }
    })

    response = yield from intent.async_handle(
        hass, 'test', 'HelloWorld', {'name': {'value': 'Paulus'}}
    )

    assert len(calls) == 1
    assert calls[0].data['hello'] == 'Paulus'

    assert response.speech['plain']['speech'] == 'Good morning Paulus'

    assert response.card['simple']['title'] == 'Hello Paulus'
    assert response.card['simple']['content'] == 'Content for Paulus'
