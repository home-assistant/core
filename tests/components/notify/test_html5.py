"""Test HTML5 notify platform."""
import json
import tempfile
from unittest.mock import patch, MagicMock

from werkzeug.test import EnvironBuilder

from homeassistant.components.http import request_class
from homeassistant.components.notify import html5

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


class TestHtml5Notify(object):
    """Tests for HTML5 notify platform."""

    def test_get_service_with_no_json(self):
        """Test empty json file."""
        hass = MagicMock()

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            service = html5.get_service(hass, {})

        assert service is not None

    def test_get_service_with_bad_json(self):
        """Test ."""
        hass = MagicMock()

        with tempfile.NamedTemporaryFile() as fp:
            fp.write('I am not JSON'.encode('utf-8'))
            fp.flush()
            hass.config.path.return_value = fp.name
            service = html5.get_service(hass, {})

        assert service is None

    @patch('pywebpush.WebPusher')
    def test_sending_message(self, mock_wp):
        """Test sending message."""
        hass = MagicMock()

        data = {
            'device': SUBSCRIPTION_1
        }

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(json.dumps(data).encode('utf-8'))
            fp.flush()
            hass.config.path.return_value = fp.name
            service = html5.get_service(hass, {'gcm_sender_id': '100'})

        assert service is not None

        service.send_message('Hello', target=['device', 'non_existing'],
                             data={'icon': 'beer.png'})

        assert len(mock_wp.mock_calls) == 2

        # WebPusher constructor
        assert mock_wp.mock_calls[0][1][0] == SUBSCRIPTION_1['subscription']

        # Call to send
        payload = json.loads(mock_wp.mock_calls[1][1][0])

        assert payload['body'] == 'Hello'
        assert payload['icon'] == 'beer.png'

    def test_registering_new_device_view(self):
        """Test that the HTML view works."""
        hass = MagicMock()

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            fp.close()
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == fp.name
            assert view.registrations == {}

            builder = EnvironBuilder(method='POST',
                                     data=json.dumps(SUBSCRIPTION_1))
            Request = request_class()
            resp = view.post(Request(builder.get_environ()))

            expected = {
                'unnamed device': SUBSCRIPTION_1,
            }

            assert resp.status_code == 200, resp.response
            assert view.registrations == expected
            with open(fp.name) as fpp:
                assert json.load(fpp) == expected

    def test_registering_new_device_validation(self):
        """Test various errors when registering a new device."""
        hass = MagicMock()

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]

            Request = request_class()

            builder = EnvironBuilder(method='POST', data=json.dumps({
                'browser': 'invalid browser',
                'subscription': 'sub info',
            }))
            resp = view.post(Request(builder.get_environ()))
            assert resp.status_code == 400, resp.response

            builder = EnvironBuilder(method='POST', data=json.dumps({
                'browser': 'chrome',
            }))
            resp = view.post(Request(builder.get_environ()))
            assert resp.status_code == 400, resp.response

            builder = EnvironBuilder(method='POST', data=json.dumps({
                'browser': 'chrome',
                'subscription': 'sub info',
            }))
            with patch('homeassistant.components.notify.html5._save_config',
                       return_value=False):
                resp = view.post(Request(builder.get_environ()))
            assert resp.status_code == 400, resp.response

    def test_unregistering_device_view(self):
        """Test that the HTML unregister view works."""
        hass = MagicMock()

        config = {
            'some device': SUBSCRIPTION_1,
            'other device': SUBSCRIPTION_2,
        }

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            fp.write(json.dumps(config).encode('utf-8'))
            fp.flush()
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == fp.name
            assert view.registrations == config

            builder = EnvironBuilder(method='DELETE', data=json.dumps({
                'subscription': SUBSCRIPTION_1['subscription'],
            }))
            Request = request_class()
            resp = view.delete(Request(builder.get_environ()))

            config.pop('some device')

            assert resp.status_code == 200, resp.response
            assert view.registrations == config
            with open(fp.name) as fpp:
                assert json.load(fpp) == config

    def test_unregistering_device_view_handles_unknown_subscription(self):
        """Test that the HTML unregister view handles unknown subscriptions."""
        hass = MagicMock()

        config = {
            'some device': SUBSCRIPTION_1,
            'other device': SUBSCRIPTION_2,
        }

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            fp.write(json.dumps(config).encode('utf-8'))
            fp.flush()
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == fp.name
            assert view.registrations == config

            builder = EnvironBuilder(method='DELETE', data=json.dumps({
                'subscription': SUBSCRIPTION_3['subscription']
            }))
            Request = request_class()
            resp = view.delete(Request(builder.get_environ()))

            assert resp.status_code == 200, resp.response
            assert view.registrations == config
            with open(fp.name) as fpp:
                assert json.load(fpp) == config

    def test_unregistering_device_view_handles_json_safe_error(self):
        """Test that the HTML unregister view handles JSON write errors."""
        hass = MagicMock()

        config = {
            'some device': SUBSCRIPTION_1,
            'other device': SUBSCRIPTION_2,
        }

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            fp.write(json.dumps(config).encode('utf-8'))
            fp.flush()
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[1][1][0]
            assert view.json_path == fp.name
            assert view.registrations == config

            builder = EnvironBuilder(method='DELETE', data=json.dumps({
                'subscription': SUBSCRIPTION_1['subscription'],
            }))
            Request = request_class()

            with patch('homeassistant.components.notify.html5._save_config',
                       return_value=False):
                resp = view.delete(Request(builder.get_environ()))

            assert resp.status_code == 500, resp.response
            assert view.registrations == config
            with open(fp.name) as fpp:
                assert json.load(fpp) == config

    def test_callback_view_no_jwt(self):
        """Test that the notification callback view works without JWT."""
        hass = MagicMock()

        with tempfile.NamedTemporaryFile() as fp:
            hass.config.path.return_value = fp.name
            fp.close()
            service = html5.get_service(hass, {})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            view = hass.mock_calls[2][1][0]

            builder = EnvironBuilder(method='POST', data=json.dumps({
                'type': 'push',
                'tag': '3bc28d69-0921-41f1-ac6a-7a627ba0aa72'
            }))
            Request = request_class()
            resp = view.post(Request(builder.get_environ()))

            assert resp.status_code == 401, resp.response

    @patch('pywebpush.WebPusher')
    def test_callback_view_with_jwt(self, mock_wp):
        """Test that the notification callback view works with JWT."""
        hass = MagicMock()

        data = {
            'device': SUBSCRIPTION_1,
        }

        with tempfile.NamedTemporaryFile() as fp:
            fp.write(json.dumps(data).encode('utf-8'))
            fp.flush()
            hass.config.path.return_value = fp.name
            service = html5.get_service(hass, {'gcm_sender_id': '100'})

            assert service is not None

            # assert hass.called
            assert len(hass.mock_calls) == 3

            service.send_message('Hello', target=['device'],
                                 data={'icon': 'beer.png'})

            assert len(mock_wp.mock_calls) == 2

            # WebPusher constructor
            assert mock_wp.mock_calls[0][1][0] == \
                SUBSCRIPTION_1['subscription']

            # Call to send
            push_payload = json.loads(mock_wp.mock_calls[1][1][0])

            assert push_payload['body'] == 'Hello'
            assert push_payload['icon'] == 'beer.png'

            view = hass.mock_calls[2][1][0]
            view.registrations = data

            bearer_token = "Bearer {}".format(push_payload['data']['jwt'])

            builder = EnvironBuilder(method='POST', data=json.dumps({
                'type': 'push',
            }), headers={'Authorization': bearer_token})
            Request = request_class()
            resp = view.post(Request(builder.get_environ()))

            assert resp.status_code == 200, resp.response
            returned = resp.response[0].decode('utf-8')
            expected = '{"event": "push", "status": "ok"}'
            assert json.loads(returned) == json.loads(expected)
