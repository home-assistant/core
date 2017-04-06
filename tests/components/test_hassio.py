"""The tests for the hassio component."""
import asyncio
import os

import aiohttp

import homeassistant.components.hassio as ho
from homeassistant.setup import setup_component

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

    def test_setup_component(self):
        """Test setup component."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

    def test_setup_component_test_service(self):
        """Test setup component and check if service exits."""
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
            'data': None,
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_rest_command_timeout(self, aioclient_mock):
        """Call a hassio with timeout."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), exc=asyncio.TimeoutError())

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_aiohttp_error(self, aioclient_mock):
        """Call a hassio with aiohttp exception."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), exc=aiohttp.ClientError())

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_error(self, aioclient_mock):
        """Call a hassio with status code 503."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), status=503)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_error_api(self, aioclient_mock):
        """Call a hassio with status code 503."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), json=self.error_msg)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_host_reboot(self, aioclient_mock):
        """Call a hassio for host reboot."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/reboot"), json=self.ok_msg)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_REBOOT, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_host_shutdown(self, aioclient_mock):
        """Call a hassio for host shutdown."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/shutdown"), json=self.ok_msg)

        self.hass.services.call(ho.DOMAIN, ho.SERVICE_HOST_SHUTDOWN, {})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_host_update(self, aioclient_mock):
        """Call a hassio for host update."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("host/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_HOST_UPDATE, {'version': '0.4'})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['version'] == '0.4'

    def test_rest_command_http_supervisor_update(self, aioclient_mock):
        """Call a hassio for supervisor update."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("supervisor/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_SUPERVISOR_UPDATE, {'version': '0.4'})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['version'] == '0.4'

    def test_rest_command_http_homeassistant_update(self, aioclient_mock):
        """Call a hassio for homeassistant update."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("homeassistant/update"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_HOMEASSISTANT_UPDATE, {'version': '0.4'})
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['version'] == '0.4'

    def test_rest_command_http_addon_install(self, aioclient_mock):
        """Call a hassio for addon install."""
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

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['version'] == '0.4'

    def test_rest_command_http_addon_uninstall(self, aioclient_mock):
        """Call a hassio for addon uninstall."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/uninstall"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_UNINSTALL, {
                'addon': 'smb_config'
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_addon_update(self, aioclient_mock):
        """Call a hassio for addon update."""
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

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['version'] == '0.4'

    def test_rest_command_http_addon_start(self, aioclient_mock):
        """Call a hassio for addon start."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/start"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_START, {
                'addon': 'smb_config',
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    def test_rest_command_http_addon_stop(self, aioclient_mock):
        """Call a hassio for addon stop."""
        with assert_setup_component(0, ho.DOMAIN):
            setup_component(self.hass, ho.DOMAIN, self.config)

        aioclient_mock.get(
            self.url.format("addons/smb_config/stop"), json=self.ok_msg)

        self.hass.services.call(
            ho.DOMAIN, ho.SERVICE_ADDON_STOP, {
                'addon': 'smb_config'
            })
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
