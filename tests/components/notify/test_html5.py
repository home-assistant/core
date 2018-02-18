"""Test HTML5 notify platform."""
import asyncio
import json
from unittest.mock import patch, MagicMock, mock_open
from aiohttp.hdrs import AUTHORIZATION

from homeassistant.setup import async_setup_component
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.notify import html5

CONFIG_FILE = 'file.conf'

SUBSCRIPTION_1 = {
    'browser': 'chrome',
    'subscription': {
        'endpoint': 'https://google.com',
        'keys': {'auth': 'auth', 'p256dh': 'p256dh'}
    },
}
SUBSCRIPTION_2 = {
    'browser': 'firefox',
    'subscription': {
        'endpoint': 'https://example.com',
        'keys': {
            'auth': 'bla',
            'p256dh': 'bla',
        },
    },
}
SUBSCRIPTION_3 = {
    'browser': 'chrome',
    'subscription': {
        'endpoint': 'https://example.com/not_exist',
        'keys': {
            'auth': 'bla',
            'p256dh': 'bla',
        },
    },
}
SUBSCRIPTION_4 = {
    'browser': 'chrome',
    'subscription': {
        'endpoint': 'https://google.com',
        'expirationTime': None,
        'keys': {'auth': 'auth', 'p256dh': 'p256dh'}
    },
}

REGISTER_URL = '/api/notify.html5'
PUBLISH_URL = '/api/notify.html5/callback'


@asyncio.coroutine
def mock_client(hass, test_client, registrations=None):
    """Create a test client for HTML5 views."""
    if registrations is None:
        registrations = {}

    with patch('homeassistant.components.notify.html5._load_config',
               return_value=registrations):
        yield from async_setup_component(hass, 'notify', {
            'notify': {
                'platform': 'html5'
            }
        })

    return (yield from test_client(hass.http.app))


class TestHtml5Notify(object):
    """Tests for HTML5 notify platform."""

    def test_get_service_with_no_json(self):
        """Test empty json file."""
        hass = MagicMock()

        m = mock_open()
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            service = html5.get_service(hass, {})

        assert service is not None

    @patch('pywebpush.WebPusher')
    def test_sending_message(self, mock_wp):
        """Test sending message."""
        hass = MagicMock()

        data = {
            'device': SUBSCRIPTION_1
        }

        m = mock_open(read_data=json.dumps(data))
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            service = html5.get_service(hass, {'gcm_sender_id': '100'})

        assert service is not None

        service.send_message('Hello', target=['device', 'non_existing'],
                             data={'icon': 'beer.png'})

        assert len(mock_wp.mock_calls) == 3

        # WebPusher constructor
        assert mock_wp.mock_calls[0][1][0] == SUBSCRIPTION_1['subscription']
        # Third mock_call checks the status_code of the response.
        assert mock_wp.mock_calls[2][0] == '().send().status_code.__eq__'

        # Call to send
        payload = json.loads(mock_wp.mock_calls[1][1][0])

        assert payload['body'] == 'Hello'
        assert payload['icon'] == 'beer.png'


@asyncio.coroutine
def test_registering_new_device_view(hass, test_client):
    """Test that the HTML view works."""
    client = yield from mock_client(hass, test_client)

    with patch('homeassistant.components.notify.html5.save_json') as mock_save:
        resp = yield from client.post(REGISTER_URL,
                                      data=json.dumps(SUBSCRIPTION_1))

    assert resp.status == 200
    assert len(mock_save.mock_calls) == 1
    assert mock_save.mock_calls[0][1][1] == {
        'unnamed device': SUBSCRIPTION_1,
    }


@asyncio.coroutine
def test_registering_new_device_expiration_view(hass, test_client):
    """Test that the HTML view works."""
    client = yield from mock_client(hass, test_client)

    with patch('homeassistant.components.notify.html5.save_json') as mock_save:
        resp = yield from client.post(REGISTER_URL,
                                      data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == 200
    assert mock_save.mock_calls[0][1][1] == {
        'unnamed device': SUBSCRIPTION_4,
    }


@asyncio.coroutine
def test_registering_new_device_fails_view(hass, test_client):
    """Test subs. are not altered when registering a new device fails."""
    registrations = {}
    client = yield from mock_client(hass, test_client, registrations)

    with patch('homeassistant.components.notify.html5.save_json',
               side_effect=HomeAssistantError()):
        resp = yield from client.post(REGISTER_URL,
                                      data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == 500
    assert registrations == {}


@asyncio.coroutine
def test_registering_existing_device_view(hass, test_client):
    """Test subscription is updated when registering existing device."""
    registrations = {}
    client = yield from mock_client(hass, test_client, registrations)

    with patch('homeassistant.components.notify.html5.save_json') as mock_save:
        yield from client.post(REGISTER_URL,
                               data=json.dumps(SUBSCRIPTION_1))
        resp = yield from client.post(REGISTER_URL,
                                      data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == 200
    assert mock_save.mock_calls[0][1][1] == {
        'unnamed device': SUBSCRIPTION_4,
    }
    assert registrations == {
        'unnamed device': SUBSCRIPTION_4,
    }


@asyncio.coroutine
def test_registering_existing_device_fails_view(hass, test_client):
    """Test sub. is not updated when registering existing device fails."""
    registrations = {}
    client = yield from mock_client(hass, test_client, registrations)

    with patch('homeassistant.components.notify.html5.save_json') as mock_save:
        yield from client.post(REGISTER_URL,
                               data=json.dumps(SUBSCRIPTION_1))
        mock_save.side_effect = HomeAssistantError
        resp = yield from client.post(REGISTER_URL,
                                      data=json.dumps(SUBSCRIPTION_4))

    assert resp.status == 500
    assert registrations == {
        'unnamed device': SUBSCRIPTION_1,
    }


@asyncio.coroutine
def test_registering_new_device_validation(hass, test_client):
    """Test various errors when registering a new device."""
    client = yield from mock_client(hass, test_client)

    resp = yield from client.post(REGISTER_URL, data=json.dumps({
        'browser': 'invalid browser',
        'subscription': 'sub info',
    }))
    assert resp.status == 400

    resp = yield from client.post(REGISTER_URL, data=json.dumps({
        'browser': 'chrome',
    }))
    assert resp.status == 400

    with patch('homeassistant.components.notify.html5.save_json',
               return_value=False):
        resp = yield from client.post(REGISTER_URL, data=json.dumps({
            'browser': 'chrome',
            'subscription': 'sub info',
        }))
    assert resp.status == 400


@asyncio.coroutine
def test_unregistering_device_view(hass, test_client):
    """Test that the HTML unregister view works."""
    registrations = {
        'some device': SUBSCRIPTION_1,
        'other device': SUBSCRIPTION_2,
    }
    client = yield from mock_client(hass, test_client, registrations)

    with patch('homeassistant.components.notify.html5.save_json') as mock_save:
        resp = yield from client.delete(REGISTER_URL, data=json.dumps({
            'subscription': SUBSCRIPTION_1['subscription'],
        }))

    assert resp.status == 200
    assert len(mock_save.mock_calls) == 1
    assert registrations == {
        'other device': SUBSCRIPTION_2
    }


@asyncio.coroutine
def test_unregister_device_view_handle_unknown_subscription(hass, test_client):
    """Test that the HTML unregister view handles unknown subscriptions."""
    registrations = {}
    client = yield from mock_client(hass, test_client, registrations)

    with patch('homeassistant.components.notify.html5.save_json') as mock_save:
        resp = yield from client.delete(REGISTER_URL, data=json.dumps({
            'subscription': SUBSCRIPTION_3['subscription']
        }))

    assert resp.status == 200, resp.response
    assert registrations == {}
    assert len(mock_save.mock_calls) == 0


@asyncio.coroutine
def test_unregistering_device_view_handles_save_error(hass, test_client):
    """Test that the HTML unregister view handles save errors."""
    registrations = {
        'some device': SUBSCRIPTION_1,
        'other device': SUBSCRIPTION_2,
    }
    client = yield from mock_client(hass, test_client, registrations)

    with patch('homeassistant.components.notify.html5.save_json',
               side_effect=HomeAssistantError()):
        resp = yield from client.delete(REGISTER_URL, data=json.dumps({
            'subscription': SUBSCRIPTION_1['subscription'],
        }))

    assert resp.status == 500, resp.response
    assert registrations == {
        'some device': SUBSCRIPTION_1,
        'other device': SUBSCRIPTION_2,
    }


@asyncio.coroutine
def test_callback_view_no_jwt(hass, test_client):
    """Test that the notification callback view works without JWT."""
    client = yield from mock_client(hass, test_client)
    resp = yield from client.post(PUBLISH_URL, data=json.dumps({
        'type': 'push',
        'tag': '3bc28d69-0921-41f1-ac6a-7a627ba0aa72'
    }))

    assert resp.status == 401, resp.response


@asyncio.coroutine
def test_callback_view_with_jwt(hass, test_client):
    """Test that the notification callback view works with JWT."""
    registrations = {
        'device': SUBSCRIPTION_1
    }
    client = yield from mock_client(hass, test_client, registrations)

    with patch('pywebpush.WebPusher') as mock_wp:
        yield from hass.services.async_call('notify', 'notify', {
            'message': 'Hello',
            'target': ['device'],
            'data': {'icon': 'beer.png'}
        }, blocking=True)

    assert len(mock_wp.mock_calls) == 3

    # WebPusher constructor
    assert mock_wp.mock_calls[0][1][0] == \
        SUBSCRIPTION_1['subscription']
    # Third mock_call checks the status_code of the response.
    assert mock_wp.mock_calls[2][0] == '().send().status_code.__eq__'

    # Call to send
    push_payload = json.loads(mock_wp.mock_calls[1][1][0])

    assert push_payload['body'] == 'Hello'
    assert push_payload['icon'] == 'beer.png'

    bearer_token = "Bearer {}".format(push_payload['data']['jwt'])

    resp = yield from client.post(PUBLISH_URL, json={
        'type': 'push',
    }, headers={AUTHORIZATION: bearer_token})

    assert resp.status == 200
    body = yield from resp.json()
    assert body == {"event": "push", "status": "ok"}
