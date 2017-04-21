"""The tests for the hassio component."""
import asyncio
import os

import aiohttp

import homeassistant.components.hassio as ho
from homeassistant.setup import setup_component, async_setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)


class TestHassIOSetup(object):
    """Test the hassio component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            ho.DOMAIN: {},
        }

        os.environ['HASSIO'] = "127.0.0.1"

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self, aioclient_mock):
        """Test setup component."""
        aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
            'result': 'ok', 'data': {}
        })
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

    def test_setup_component_test_service(self, aioclient_mock):
        """Test setup component and check if service exits."""
        aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
            'result': 'ok', 'data': {}
        })
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_HOST_REBOOT)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_HOST_SHUTDOWN)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_HOST_UPDATE)

        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_SUPERVISOR_UPDATE)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_SUPERVISOR_RELOAD)

        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_ADDON_INSTALL)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_ADDON_UNINSTALL)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_ADDON_UPDATE)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_ADDON_START)
        assert self.hass.services.has_service(
            ho.DOMAIN, ho.SERVICE_ADDON_STOP)


class TestHassIOComponent(object):
    """Test the HassIO component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = {
            ho.DOMAIN: {},
        }

        os.environ['HASSIO'] = "127.0.0.1"
        self.url = "http://127.0.0.1/{}"

        self.error_msg = {
            'result': 'error',
            'message': 'Test error',
        }
        self.ok_msg = {
            'result': 'ok',
            'data': {},
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_rest_command_timeout(self, aioclient_mock):
        """Call a hassio with timeout."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), exc=asyncio.TimeoutError())

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_aiohttp_error(self, aioclient_mock):
        """Call a hassio with aiohttp exception."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), exc=aiohttp.ClientError())

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_error(self, aioclient_mock):
        """Call a hassio with status code 503."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), status=503)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_error_api(self, aioclient_mock):
        """Call a hassio with status code 503."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), json=self.error_msg)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_host_reboot(self, aioclient_mock):
        """Call a hassio for host reboot."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/reboot"), json=self.ok_msg)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_REBOOT, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_host_shutdown(self, aioclient_mock):
        """Call a hassio for host shutdown."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/shutdown"), json=self.ok_msg)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_SHUTDOWN, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_host_update(self, aioclient_mock):
        """Call a hassio for host update."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {'version': '0.4'})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[-1][2]['version'] == '0.4'

    def test_rest_command_http_supervisor_update(self, aioclient_mock):
        """Call a hassio for supervisor update."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("supervisor/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_SUPERVISOR_UPDATE, {'version': '0.4'})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[-1][2]['version'] == '0.4'

    def test_rest_command_http_supervisor_reload(self, aioclient_mock):
        """Call a hassio for supervisor reload."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("supervisor/reload"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_SUPERVISOR_RELOAD, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_homeassistant_update(self, aioclient_mock):
        """Call a hassio for homeassistant update."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("homeassistant/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_HOMEASSISTANT_UPDATE, {'version': '0.4'})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[-1][2]['version'] == '0.4'

    def test_rest_command_http_addon_install(self, aioclient_mock):
        """Call a hassio for addon install."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/install"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_INSTALL, {
                'addon': 'smb_config',
                'version': '0.4'
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[-1][2]['version'] == '0.4'

    def test_rest_command_http_addon_uninstall(self, aioclient_mock):
        """Call a hassio for addon uninstall."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/uninstall"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_UNINSTALL, {
                'addon': 'smb_config'
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_addon_update(self, aioclient_mock):
        """Call a hassio for addon update."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_UPDATE, {
                'addon': 'smb_config',
                'version': '0.4'
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[-1][2]['version'] == '0.4'

    def test_rest_command_http_addon_start(self, aioclient_mock):
        """Call a hassio for addon start."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/start"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_START, {
                'addon': 'smb_config',
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2

    def test_rest_command_http_addon_stop(self, aioclient_mock):
        """Call a hassio for addon stop."""
        aioclient_mock.get(
            "http://127.0.0.1/supervisor/ping", json=self.ok_msg)
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/stop"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_STOP, {
                'addon': 'smb_config'
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2


@asyncio.coroutine
def test_async_hassio_host_view(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    os.environ['HASSIO'] = "127.0.0.1"

    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
        'result': 'ok', 'data': {}
    })
    result = yield from async_setup_component(hass, ho.DOMAIN, {ho.DOMAIN: {}})
    assert result, 'Failed to setup hasio'

    client = yield from test_client(hass.http.app)

    aioclient_mock.get('http://127.0.0.1/host/info', json={
        'result': 'ok',
        'data': {
            'os': 'resinos',
            'version': '0.3',
            'current': '0.4',
            'level': 16,
            'hostname': 'test',
        }
    })

    resp = yield from client.get('/api/hassio/host')
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 2
    assert resp.status == 200
    assert data['os'] == 'resinos'
    assert data['version'] == '0.3'
    assert data['current'] == '0.4'
    assert data['level'] == 16
    assert data['hostname'] == 'test'


@asyncio.coroutine
def test_async_hassio_homeassistant_view(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    os.environ['HASSIO'] = "127.0.0.1"

    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
        'result': 'ok', 'data': {}
    })
    result = yield from async_setup_component(hass, ho.DOMAIN, {ho.DOMAIN: {}})
    assert result, 'Failed to setup hasio'

    client = yield from test_client(hass.http.app)

    aioclient_mock.get('http://127.0.0.1/homeassistant/info', json={
        'result': 'ok',
        'data': {
            'version': '0.41',
            'current': '0.41.1',
        }
    })

    resp = yield from client.get('/api/hassio/homeassistant')
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 2
    assert resp.status == 200
    assert data['version'] == '0.41'
    assert data['current'] == '0.41.1'


@asyncio.coroutine
def test_async_hassio_supervisor_view(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    os.environ['HASSIO'] = "127.0.0.1"

    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
        'result': 'ok', 'data': {}
    })
    result = yield from async_setup_component(hass, ho.DOMAIN, {ho.DOMAIN: {}})
    assert result, 'Failed to setup hasio'

    client = yield from test_client(hass.http.app)

    aioclient_mock.get('http://127.0.0.1/supervisor/info', json={
        'result': 'ok',
        'data': {
            'version': '0.3',
            'current': '0.4',
            'beta': False,
        }
    })

    resp = yield from client.get('/api/hassio/supervisor')
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 2
    assert resp.status == 200
    assert data['version'] == '0.3'
    assert data['current'] == '0.4'
    assert not data['beta']

    aioclient_mock.get('http://127.0.0.1/supervisor/options', json={
        'result': 'ok',
        'data': {},
    })

    resp = yield from client.post('/api/hassio/supervisor', json={
        'beta': True,
    })
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 3
    assert resp.status == 200
    assert aioclient_mock.mock_calls[-1][2]['beta']


@asyncio.coroutine
def test_async_hassio_network_view(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    os.environ['HASSIO'] = "127.0.0.1"

    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
        'result': 'ok', 'data': {}
    })
    result = yield from async_setup_component(hass, ho.DOMAIN, {ho.DOMAIN: {}})
    assert result, 'Failed to setup hasio'

    client = yield from test_client(hass.http.app)

    aioclient_mock.get('http://127.0.0.1/network/info', json={
        'result': 'ok',
        'data': {
            'mode': 'dhcp',
            'ssid': 'my_wlan',
            'password': '123456',
        }
    })

    resp = yield from client.get('/api/hassio/network')
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 2
    assert resp.status == 200
    assert data['mode'] == 'dhcp'
    assert data['ssid'] == 'my_wlan'
    assert data['password'] == '123456'

    aioclient_mock.get('http://127.0.0.1/network/options', json={
        'result': 'ok',
        'data': {},
    })

    resp = yield from client.post('/api/hassio/network', json={
        'mode': 'dhcp',
        'ssid': 'my_wlan2',
        'password': '654321',
    })
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 3
    assert resp.status == 200
    assert aioclient_mock.mock_calls[-1][2]['ssid'] == 'my_wlan2'
    assert aioclient_mock.mock_calls[-1][2]['password'] == '654321'


@asyncio.coroutine
def test_async_hassio_addon_view(aioclient_mock, hass, test_client):
    """Test that it fetches the given url."""
    os.environ['HASSIO'] = "127.0.0.1"

    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={
        'result': 'ok', 'data': {}
    })
    result = yield from async_setup_component(hass, ho.DOMAIN, {ho.DOMAIN: {}})
    assert result, 'Failed to setup hasio'

    client = yield from test_client(hass.http.app)

    aioclient_mock.get('http://127.0.0.1/addons/smb_config/info', json={
        'result': 'ok',
        'data': {
            'name': 'SMB Config',
            'state': 'running',
            'boot': 'auto',
            'options': {
                'bla': False,
            }
        }
    })

    resp = yield from client.get('/api/hassio/addons/smb_config')
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 2
    assert resp.status == 200
    assert data['name'] == 'SMB Config'
    assert data['state'] == 'running'
    assert data['boot'] == 'auto'
    assert not data['options']['bla']

    aioclient_mock.get('http://127.0.0.1/addons/smb_config/options', json={
        'result': 'ok',
        'data': {},
    })

    resp = yield from client.post('/api/hassio/addons/smb_config', json={
        'boot': 'manual',
        'options': {
            'bla': True,
        }
    })
    data = yield from resp.json()

    assert len(aioclient_mock.mock_calls) == 3
    assert resp.status == 200
    assert aioclient_mock.mock_calls[-1][2]['boot'] == 'manual'
    assert aioclient_mock.mock_calls[-1][2]['options']['bla']
