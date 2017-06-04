"""Test hassbian config."""
import asyncio
import os
from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config.hassbian import (
    HassbianSuitesView, HassbianSuiteInstallView)


def test_setup_check_env_prevents_load(hass, loop):
    """Test it does not set up hassbian if environment var not present."""
    with patch.dict(os.environ, clear=True), \
            patch.object(config, 'SECTIONS', ['hassbian']), \
            patch('homeassistant.components.http.'
                  'HomeAssistantWSGI.register_view') as reg_view:
        loop.run_until_complete(async_setup_component(hass, 'config', {}))
    assert 'config' in hass.config.components
    assert reg_view.called is False


def test_setup_check_env_works(hass, loop):
    """Test it sets up hassbian if environment var present."""
    with patch.dict(os.environ, {'FORCE_HASSBIAN': '1'}), \
            patch.object(config, 'SECTIONS', ['hassbian']), \
            patch('homeassistant.components.http.'
                  'HomeAssistantWSGI.register_view') as reg_view:
        loop.run_until_complete(async_setup_component(hass, 'config', {}))
    assert 'config' in hass.config.components
    assert len(reg_view.mock_calls) == 2
    assert isinstance(reg_view.mock_calls[0][1][0], HassbianSuitesView)
    assert isinstance(reg_view.mock_calls[1][1][0], HassbianSuiteInstallView)


@asyncio.coroutine
def test_get_suites(hass, test_client):
    """Test getting suites."""
    with patch.dict(os.environ, {'FORCE_HASSBIAN': '1'}), \
            patch.object(config, 'SECTIONS', ['hassbian']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)
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
    with patch.dict(os.environ, {'FORCE_HASSBIAN': '1'}), \
            patch.object(config, 'SECTIONS', ['hassbian']):
        yield from async_setup_component(hass, 'config', {})

    client = yield from test_client(hass.http.app)
    resp = yield from client.post(
        '/api/config/hassbian/suites/openzwave/install')
    assert resp.status == 200
    result = yield from resp.json()

    assert result == {"status": "ok"}
