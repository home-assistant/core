"""Test Z-Wave config panel."""
import asyncio
import json
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config


VIEW_NAME = 'api:config:zwave:device_config'


@asyncio.coroutine
def test_get_device_config(hass, test_client):
    """Test getting device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

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

    with patch('homeassistant.components.config._read', mock_read):
        resp = yield from client.get(
            '/api/config/zwave/device_config/hello.beer')

    assert resp.status == 200
    result = yield from resp.json()

    assert result == {'free': 'beer'}


@asyncio.coroutine
def test_update_device_config(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

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

    with patch('homeassistant.components.config._read', mock_read), \
            patch('homeassistant.components.config._write', mock_write):
        resp = yield from client.post(
            '/api/config/zwave/device_config/hello.beer', data=json.dumps({
                'polling_intensity': 2
            }))

    assert resp.status == 200
    result = yield from resp.json()
    assert result == {'result': 'ok'}

    orig_data['hello.beer']['polling_intensity'] = 2

    assert written[0] == orig_data


@asyncio.coroutine
def test_update_device_config_invalid_key(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    resp = yield from client.post(
        '/api/config/zwave/device_config/invalid_entity', data=json.dumps({
            'polling_intensity': 2
        }))

    assert resp.status == 400


@asyncio.coroutine
def test_update_device_config_invalid_data(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    resp = yield from client.post(
        '/api/config/zwave/device_config/hello.beer', data=json.dumps({
            'invalid_option': 2
        }))

    assert resp.status == 400


@asyncio.coroutine
def test_update_device_config_invalid_json(hass, test_client):
    """Test updating device config."""
    with patch.object(config, 'SECTIONS', ['zwave']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)

    resp = yield from client.post(
        '/api/config/zwave/device_config/hello.beer', data='not json')

    assert resp.status == 400
