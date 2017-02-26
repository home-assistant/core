"""Test hassbian config."""
import asyncio
import os
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config.hassbian import (
    HassbianSuitesView, HassbianSuiteInstallView)
from tests.common import (
    mock_http_component, mock_http_component_app)


def test_setup_check_env_prevents_load(hass, loop):
    """Test it does not set up hassbian if environment var not present."""
    mock_http_component(hass)
    with patch.dict(os.environ, clear=True), \
            patch.object(config, 'SECTIONS', ['hassbian']):
        loop.run_until_complete(async_setup_component(hass, 'config', {}))
    assert 'config' in hass.config.components
    assert HassbianSuitesView.name not in hass.http.views
    assert HassbianSuiteInstallView.name not in hass.http.views


def test_setup_check_env_works(hass, loop):
    """Test it sets up hassbian if environment var present."""
    mock_http_component(hass)
    with patch.dict(os.environ, {'FORCE_HASSBIAN': '1'}), \
            patch.object(config, 'SECTIONS', ['hassbian']):
        loop.run_until_complete(async_setup_component(hass, 'config', {}))
    assert 'config' in hass.config.components
    assert HassbianSuitesView.name in hass.http.views
    assert HassbianSuiteInstallView.name in hass.http.views


@asyncio.coroutine
def test_get_suites(hass, test_client):
    """Test getting suites."""
    app = mock_http_component_app(hass)

    with patch.dict(os.environ, {'FORCE_HASSBIAN': '1'}), \
            patch.object(config, 'SECTIONS', ['hassbian']):
        yield from async_setup_component(hass, 'config', {})

    hass.http.views[HassbianSuitesView.name].register(app.router)

    client = yield from test_client(app)
    resp = yield from client.get('/api/config/hassbian/suites')
    assert resp.status == 200
    result = yield from resp.json()

    assert 'mosquitto' in result
    info = result['mosquitto']
    assert info['state'] == 'failed'
    assert info['description'] == \
        'Installs the Mosquitto package for setting up a local MQTT server'


@asyncio.coroutine
def test_install_suite(hass, test_client):
    """Test getting suites."""
    app = mock_http_component_app(hass)

    with patch.dict(os.environ, {'FORCE_HASSBIAN': '1'}), \
            patch.object(config, 'SECTIONS', ['hassbian']):
        yield from async_setup_component(hass, 'config', {})

    hass.http.views[HassbianSuiteInstallView.name].register(app.router)

    client = yield from test_client(app)
    resp = yield from client.post(
        '/api/config/hassbian/suites/openzwave/install')
    assert resp.status == 200
    result = yield from resp.json()

    assert result == {"status": "ok"}
