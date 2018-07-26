"""The tests for Home Assistant frontend."""
import asyncio
import re
from unittest.mock import patch

import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.components.frontend import (
    DOMAIN, CONF_JS_VERSION, CONF_THEMES, CONF_EXTRA_HTML_URL,
    CONF_EXTRA_HTML_URL_ES5)
from homeassistant.components import websocket_api as wapi

from tests.common import mock_coro


CONFIG_THEMES = {
    DOMAIN: {
        CONF_THEMES: {
            'happy': {
                'primary-color': 'red'
            }
        }
    }
}


@pytest.fixture
def mock_http_client(hass, aiohttp_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'frontend', {}))
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def mock_http_client_with_themes(hass, aiohttp_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'frontend', {
        DOMAIN: {
            CONF_THEMES: {
                'happy': {
                    'primary-color': 'red'
                }
            }
        }}))
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
def mock_http_client_with_urls(hass, aiohttp_client):
    """Start the Hass HTTP component."""
    hass.loop.run_until_complete(async_setup_component(hass, 'frontend', {
        DOMAIN: {
            CONF_JS_VERSION: 'auto',
            CONF_EXTRA_HTML_URL: ["https://domain.com/my_extra_url.html"],
            CONF_EXTRA_HTML_URL_ES5:
                ["https://domain.com/my_extra_url_es5.html"]
        }}))
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@asyncio.coroutine
def test_frontend_and_static(mock_http_client):
    """Test if we can get the frontend."""
    resp = yield from mock_http_client.get('')
    assert resp.status == 200
    assert 'cache-control' not in resp.headers

    text = yield from resp.text()

    # Test we can retrieve frontend.js
    frontendjs = re.search(
        r'(?P<app>\/frontend_es5\/app-[A-Za-z0-9]{8}.js)', text)

    assert frontendjs is not None
    resp = yield from mock_http_client.get(frontendjs.groups(0)[0])
    assert resp.status == 200
    assert 'public' in resp.headers.get('cache-control')


@asyncio.coroutine
def test_dont_cache_service_worker(mock_http_client):
    """Test that we don't cache the service worker."""
    resp = yield from mock_http_client.get('/service_worker_es5.js')
    assert resp.status == 200
    assert 'cache-control' not in resp.headers

    resp = yield from mock_http_client.get('/service_worker.js')
    assert resp.status == 200
    assert 'cache-control' not in resp.headers


@asyncio.coroutine
def test_404(mock_http_client):
    """Test for HTTP 404 error."""
    resp = yield from mock_http_client.get('/not-existing')
    assert resp.status == 404


@asyncio.coroutine
def test_we_cannot_POST_to_root(mock_http_client):
    """Test that POST is not allow to root."""
    resp = yield from mock_http_client.post('/')
    assert resp.status == 405


@asyncio.coroutine
def test_states_routes(mock_http_client):
    """All served by index."""
    resp = yield from mock_http_client.get('/states')
    assert resp.status == 200

    resp = yield from mock_http_client.get('/states/group.existing')
    assert resp.status == 200


async def test_themes_api(hass, hass_ws_client):
    """Test that /api/themes returns correct data."""
    assert await async_setup_component(hass, 'frontend', CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await client.send_json({
        'id': 5,
        'type': 'frontend/get_themes',
    })
    msg = await client.receive_json()

    assert msg['result']['default_theme'] == 'default'
    assert msg['result']['themes'] == {'happy': {'primary-color': 'red'}}


async def test_themes_set_theme(hass, hass_ws_client):
    """Test frontend.set_theme service."""
    assert await async_setup_component(hass, 'frontend', CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        DOMAIN, 'set_theme', {'name': 'happy'}, blocking=True)

    await client.send_json({
        'id': 5,
        'type': 'frontend/get_themes',
    })
    msg = await client.receive_json()

    assert msg['result']['default_theme'] == 'happy'

    await hass.services.async_call(
        DOMAIN, 'set_theme', {'name': 'default'}, blocking=True)

    await client.send_json({
        'id': 6,
        'type': 'frontend/get_themes',
    })
    msg = await client.receive_json()

    assert msg['result']['default_theme'] == 'default'


async def test_themes_set_theme_wrong_name(hass, hass_ws_client):
    """Test frontend.set_theme service called with wrong name."""
    assert await async_setup_component(hass, 'frontend', CONFIG_THEMES)
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        DOMAIN, 'set_theme', {'name': 'wrong'}, blocking=True)

    await client.send_json({
        'id': 5,
        'type': 'frontend/get_themes',
    })

    msg = await client.receive_json()

    assert msg['result']['default_theme'] == 'default'


async def test_themes_reload_themes(hass, hass_ws_client):
    """Test frontend.reload_themes service."""
    assert await async_setup_component(hass, 'frontend', CONFIG_THEMES)
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.frontend.load_yaml_config_file',
               return_value={DOMAIN: {
                   CONF_THEMES: {
                       'sad': {'primary-color': 'blue'}
                   }}}):
        await hass.services.async_call(
            DOMAIN, 'set_theme', {'name': 'happy'}, blocking=True)
        await hass.services.async_call(DOMAIN, 'reload_themes', blocking=True)

    await client.send_json({
        'id': 5,
        'type': 'frontend/get_themes',
    })

    msg = await client.receive_json()

    assert msg['result']['themes'] == {'sad': {'primary-color': 'blue'}}
    assert msg['result']['default_theme'] == 'default'


async def test_missing_themes(hass, hass_ws_client):
    """Test that themes API works when themes are not defined."""
    await async_setup_component(hass, 'frontend')

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'frontend/get_themes',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success']
    assert msg['result']['default_theme'] == 'default'
    assert msg['result']['themes'] == {}


@asyncio.coroutine
def test_extra_urls(mock_http_client_with_urls):
    """Test that extra urls are loaded."""
    resp = yield from mock_http_client_with_urls.get('/states?latest')
    assert resp.status == 200
    text = yield from resp.text()
    assert text.find("href='https://domain.com/my_extra_url.html'") >= 0


@asyncio.coroutine
def test_extra_urls_es5(mock_http_client_with_urls):
    """Test that es5 extra urls are loaded."""
    resp = yield from mock_http_client_with_urls.get('/states?es5')
    assert resp.status == 200
    text = yield from resp.text()
    assert text.find("href='https://domain.com/my_extra_url_es5.html'") >= 0


async def test_get_panels(hass, hass_ws_client):
    """Test get_panels command."""
    await async_setup_component(hass, 'frontend')
    await hass.components.frontend.async_register_built_in_panel(
        'map', 'Map', 'mdi:account-location')

    client = await hass_ws_client(hass)
    await client.send_json({
        'id': 5,
        'type': 'get_panels',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success']
    assert msg['result']['map']['component_name'] == 'map'
    assert msg['result']['map']['url_path'] == 'map'
    assert msg['result']['map']['icon'] == 'mdi:account-location'
    assert msg['result']['map']['title'] == 'Map'


async def test_get_translations(hass, hass_ws_client):
    """Test get_translations command."""
    await async_setup_component(hass, 'frontend')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.frontend.async_get_translations',
               side_effect=lambda hass, lang: mock_coro({'lang': lang})):
        await client.send_json({
            'id': 5,
            'type': 'frontend/get_translations',
            'language': 'nl',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success']
    assert msg['result'] == {'resources': {'lang': 'nl'}}


async def test_lovelace_ui(hass, hass_ws_client):
    """Test lovelace_ui command."""
    await async_setup_component(hass, 'frontend')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.frontend.load_yaml',
               return_value={'hello': 'world'}):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success']
    assert msg['result'] == {'hello': 'world'}


async def test_lovelace_ui_not_found(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'frontend')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.frontend.load_yaml',
               side_effect=FileNotFoundError):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'file_not_found'


async def test_lovelace_ui_load_err(hass, hass_ws_client):
    """Test lovelace_ui command cannot find file."""
    await async_setup_component(hass, 'frontend')
    client = await hass_ws_client(hass)

    with patch('homeassistant.components.frontend.load_yaml',
               side_effect=HomeAssistantError):
        await client.send_json({
            'id': 5,
            'type': 'frontend/lovelace_config',
        })
        msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == wapi.TYPE_RESULT
    assert msg['success'] is False
    assert msg['error']['code'] == 'load_error'


async def test_auth_load(mock_http_client):
    """Test auth component loaded by default."""
    resp = await mock_http_client.get('/auth/providers')
    assert resp.status == 200


async def test_onboarding_load(mock_http_client):
    """Test onboarding component loaded by default."""
    resp = await mock_http_client.get('/api/onboarding')
    assert resp.status == 200
