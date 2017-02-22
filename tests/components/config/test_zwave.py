"""Test Z-Wave config panel."""
import asyncio
import json
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config.zwave import DeviceConfigView
from tests.common import mock_http_component_app


@asyncio.coroutine
def test_get_device_config(hass, test_client):
    """Test getting device config."""
    app = mock_http_component_app(hass)

    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    hass.http.views[DeviceConfigView.name].register(app.router)

    client = yield from test_client(app)

    def mock_read(path):
        """Mock reading data."""
        return {
            'hello.beer': {
                'free': 'beer',
            },
            'other.entity': {
                'do': 'something',
            },
        }

    with patch('homeassistant.components.config.zwave._read', mock_read):
        resp = yield from client.get(
            '/api/config/zwave/device_config/hello.beer')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'free': 'beer'}


@asyncio.coroutine
def test_update_device_config(hass, test_client):
    """Test updating device config."""
    app = mock_http_component_app(hass)

    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    hass.http.views[DeviceConfigView.name].register(app.router)

    client = yield from test_client(app)

    orig_data = {
        'hello.beer': {
            'ignored': True,
        },
        'other.entity': {
            'polling_intensity': 2,
        },
    }

    def mock_read(path):
        """Mock reading data."""
        return orig_data

    written = []

    def mock_write(path, data):
        """Mock writing data."""
        written.append(data)

    with patch('homeassistant.components.config.zwave._read', mock_read), \
            patch('homeassistant.components.config.zwave._write', mock_write):
        resp = yield from client.post(
            '/api/config/zwave/device_config/hello.beer', data=json.dumps({
                'polling_intensity': 2
            }))

    assert resp.status == 200
    result = yield from resp.json()
    assert result == {'result': 'ok'}

    orig_data['hello.beer']['polling_intensity'] = 2

    assert written[0] == orig_data
