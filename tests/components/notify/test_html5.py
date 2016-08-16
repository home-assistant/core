"""Test HTML5 notify platform."""
import json
import tempfile
from unittest.mock import patch, MagicMock

from werkzeug.test import EnvironBuilder

from homeassistant.components.http import request_class
from homeassistant.components.notify import html5


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
            'device': {
                'browser': 'chrome',
                'subscription': 'hello world',
            }
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
        assert mock_wp.mock_calls[0][1][0] == 'hello world'

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
            assert len(hass.mock_calls) == 2

            view = hass.mock_calls[1][1][0]
            assert view.json_path == fp.name
            assert view.registrations == {}

            builder = EnvironBuilder(method='POST', data=json.dumps({
                'browser': 'chrome',
                'subscription': 'sub info',
            }))
            Request = request_class()
            resp = view.post(Request(builder.get_environ()))

            expected = {
                'unnamed device': {
                    'browser': 'chrome',
                    'subscription': 'sub info',
                },
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
            assert len(hass.mock_calls) == 2

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
            assert resp.status_code == 500, resp.response
