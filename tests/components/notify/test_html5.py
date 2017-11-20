"""Test HTML5 notify platform."""
import asyncio
import json
from unittest.mock import patch, MagicMock, mock_open
from aiohttp.hdrs import AUTHORIZATION

from homeassistant.components.notify import html5

from tests.common import mock_http_component_app

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

        print(mock_wp.mock_calls)

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
    def test_registering_new_device_view(self, loop, test_client):
        """Test that the HTML view works."""
        hass = MagicMock()
        expected = {
            'unnamed device': SUBSCRIPTION_1,
        }

        m = mock_open()
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == hass.config.path.return_value
            assert view.registrations == {}

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False
            resp = yield from client.post(REGISTER_URL,
                                          data=json.dumps(SUBSCRIPTION_1))

            content = yield from resp.text()
            assert resp.status == 200, content
            assert view.registrations == expected
            handle = m()
            assert json.loads(handle.write.call_args[0][0]) == expected

    @asyncio.coroutine
    def test_registering_new_device_expiration_view(self, loop, test_client):
        """Test that the HTML view works."""
        hass = MagicMock()
        expected = {
            'unnamed device': SUBSCRIPTION_4,
        }

        m = mock_open()
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == hass.config.path.return_value
            assert view.registrations == {}

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False
            resp = yield from client.post(REGISTER_URL,
                                          data=json.dumps(SUBSCRIPTION_4))

            content = yield from resp.text()
            assert resp.status == 200, content
            assert view.registrations == expected
            handle = m()
            assert json.loads(handle.write.call_args[0][0]) == expected

    @asyncio.coroutine
    def test_registering_new_device_validation(self, loop, test_client):
        """Test various errors when registering a new device."""
        hass = MagicMock()

        m = mock_open()
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False

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
                # resp = view.post(Request(builder.get_environ()))
                resp = yield from client.post(REGISTER_URL, data=json.dumps({
                    'browser': 'chrome',
                    'subscription': 'sub info',
                }))

            assert resp.status == 400

    @asyncio.coroutine
    def test_unregistering_device_view(self, loop, test_client):
        """Test that the HTML unregister view works."""
        hass = MagicMock()

        config = {
            'some device': SUBSCRIPTION_1,
            'other device': SUBSCRIPTION_2,
        }

        m = mock_open(read_data=json.dumps(config))
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == hass.config.path.return_value
            assert view.registrations == config

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False

            resp = yield from client.delete(REGISTER_URL, data=json.dumps({
                'subscription': SUBSCRIPTION_1['subscription'],
            }))

            config.pop('some device')

            assert resp.status == 200, resp.response
            assert view.registrations == config
            handle = m()
            assert json.loads(handle.write.call_args[0][0]) == config

    @asyncio.coroutine
    def test_unregister_device_view_handle_unknown_subscription(
            self, loop, test_client):
        """Test that the HTML unregister view handles unknown subscriptions."""
        hass = MagicMock()

        config = {
            'some device': SUBSCRIPTION_1,
            'other device': SUBSCRIPTION_2,
        }

        m = mock_open(read_data=json.dumps(config))
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == hass.config.path.return_value
            assert view.registrations == config

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False

            resp = yield from client.delete(REGISTER_URL, data=json.dumps({
                'subscription': SUBSCRIPTION_3['subscription']
            }))

            assert resp.status == 200, resp.response
            assert view.registrations == config
            handle = m()
            assert handle.write.call_count == 0

    @asyncio.coroutine
    def test_unregistering_device_view_handles_json_safe_error(
            self, loop, test_client):
        """Test that the HTML unregister view handles JSON write errors."""
        hass = MagicMock()

        config = {
            'some device': SUBSCRIPTION_1,
            'other device': SUBSCRIPTION_2,
        }

        m = mock_open(read_data=json.dumps(config))
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == hass.config.path.return_value
            assert view.registrations == config

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False

            with patch('homeassistant.components.notify.html5.save_json',
                       return_value=False):
                resp = yield from client.delete(REGISTER_URL, data=json.dumps({
                    'subscription': SUBSCRIPTION_1['subscription'],
                }))

            assert resp.status == 500, resp.response
            assert view.registrations == config
            handle = m()
            assert handle.write.call_count == 0

    @asyncio.coroutine
    def test_callback_view_no_jwt(self, loop, test_client):
        """Test that the notification callback view works without JWT."""
        hass = MagicMock()

        m = mock_open()
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[2][1][0]

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False

            resp = yield from client.post(PUBLISH_URL, data=json.dumps({
                'type': 'push',
                'tag': '3bc28d69-0921-41f1-ac6a-7a627ba0aa72'
            }))

            assert resp.status == 401, resp.response

    @asyncio.coroutine
    def test_callback_view_with_jwt(self, loop, test_client):
        """Test that the notification callback view works with JWT."""
        hass = MagicMock()

        data = {
            'device': SUBSCRIPTION_1
        }

        m = mock_open(read_data=json.dumps(data))
        with patch(
            'homeassistant.util.json.open',
            m, create=True
        ):
            hass.config.path.return_value = 'file.conf'
            service = html5.get_service(hass, {'gcm_sender_id': '100'})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            with patch('pywebpush.WebPusher') as mock_wp:
                service.send_message(
                    'Hello', target=['device'], data={'icon': 'beer.png'})

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

            view = hass.mock_calls[2][1][0]
            view.registrations = data

            bearer_token = "Bearer {}".format(push_payload['data']['jwt'])

            hass.loop = loop
            app = mock_http_component_app(hass)
            view.register(app.router)
            client = yield from test_client(app)
            hass.http.is_banned_ip.return_value = False

            resp = yield from client.post(PUBLISH_URL, data=json.dumps({
                'type': 'push',
            }), headers={AUTHORIZATION: bearer_token})

            assert resp.status == 200
            body = yield from resp.json()
            assert body == {"event": "push", "status": "ok"}
