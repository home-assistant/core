"""The tests for the webhook automation trigger."""
from homeassistant.core import callback
from homeassistant.setup import async_setup_component


async def test_webhook_json(hass, aiohttp_client):
    """Test triggering with a JSON webhook."""
    events = []

    @callback
    def store_event(event):
        """Helepr to store events."""
        events.append(event)

    hass.bus.async_listen('test_success', store_event)

    assert await async_setup_component(hass, 'automation', {
        'automation': {
            'trigger': {
                'platform': 'webhook',
                'webhook_id': 'json_webhook'
            },
            'action': {
                'event': 'test_success',
                'event_data_template': {
                    'hello': 'yo {{ trigger.json.hello }}',
                }
            }
        }
    })

    client = await aiohttp_client(hass.http.app)

    await client.post('/api/webhook/json_webhook', json={
        'hello': 'world'
    })

    assert len(events) == 1
    assert events[0].data['hello'] == 'yo world'


async def test_webhook_post(hass, aiohttp_client):
    """Test triggering with a POST webhook."""
    events = []

    @callback
    def store_event(event):
        """Helepr to store events."""
        events.append(event)

    hass.bus.async_listen('test_success', store_event)

    assert await async_setup_component(hass, 'automation', {
        'automation': {
            'trigger': {
                'platform': 'webhook',
                'webhook_id': 'post_webhook'
            },
            'action': {
                'event': 'test_success',
                'event_data_template': {
                    'hello': 'yo {{ trigger.data.hello }}',
                }
            }
        }
    })

    client = await aiohttp_client(hass.http.app)

    await client.post('/api/webhook/post_webhook', data={
        'hello': 'world'
    })

    assert len(events) == 1
    assert events[0].data['hello'] == 'yo world'
