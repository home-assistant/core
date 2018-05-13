"""The tests for the remote_homeassistant platform."""
import asyncio
from unittest.mock import patch

from aiohttp import WSMsgType
from async_timeout import timeout
import pytest

from homeassistant.components import remote_homeassistant
from homeassistant.core import callback
from homeassistant.components import websocket_api as wapi, frontend
from homeassistant.setup import async_setup_component, setup_component
from homeassistant.components import http

from tests.common import (
    get_test_home_assistant,
    mock_mqtt_component,
    fire_mqtt_message,
    mock_state_change_event,
    fire_time_changed
)

instance01_port = 8124
instance02_port = 8125

class TestRemoteHomeassistant(object):
    """Test the Remote Homeassistant module."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass_instance01 = get_test_home_assistant()
        #self.hass_instance02 = get_test_home_assistant()

        self.hass_main = get_test_home_assistant()

        #self.hass_main.block_till_done()

        #setup_component(
        #    self.hass_instance01, http.DOMAIN, {
        #        http.DOMAIN: {
        #            http.CONF_SERVER_PORT: instance01_port,
        #        }
        #    }
        #)

        #setup_component(self.hass_instance01, 'websocket_api')

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass_main.stop()
        self.hass_instance01.stop()
        #self.hass_instance02.stop()

        pass

    def test_connect(self):
        #setup_component(
        #    self.hass_instance01, http.DOMAIN, {
        #        http.DOMAIN: {
                   # http.CONF_SERVER_PORT: instance01_port,
        #        }
        #    }
        #)

        #setup_component(self.hass_instance01, 'websocket_api')

        #self.hass_instance01.block_till_done()


        #config = {
        #    remote_homeassistant.CONF_INSTANCES:
        #        [
        #            {
        #                remote_homeassistant.CONF_HOST: 'localhost',
        #                #remote_homeassistant.CONF_PORT: instance01_port
        #            }
        #        ]
        #}
        #setup_component(self.hass_main, remote_homeassistant.DOMAIN, {
        #    remote_homeassistant.DOMAIN: config})

        #self.hass_main.block_till_done()
        pass

