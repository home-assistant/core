"""Test the aiohttp client helper."""
import unittest

import aiohttp

import homeassistant.helpers.aiohttp_client as client
from homeassistant.util.async import run_callback_threadsafe

from tests.common import get_test_home_assistant


class TestHelpersAiohttpClient(unittest.TestCase):
    """Test homeassistant.helpers.aiohttp_client module."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_get_clientsession_with_ssl(self):
        """Test init clientsession with ssl."""
        run_callback_threadsafe(self.hass.loop, client.async_get_clientsession,
                                self.hass).result()

        assert isinstance(
            self.hass.data[client.DATA_CLIENTSESSION], aiohttp.ClientSession)
        assert isinstance(
            self.hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)

    def test_get_clientsession_without_ssl(self):
        """Test init clientsession without ssl."""
        run_callback_threadsafe(self.hass.loop, client.async_get_clientsession,
                                self.hass, False).result()

        assert isinstance(
            self.hass.data[client.DATA_CLIENTSESSION_NOTVERIFY],
            aiohttp.ClientSession)
        assert isinstance(
            self.hass.data[client.DATA_CONNECTOR_NOTVERIFY],
            aiohttp.TCPConnector)

    def test_create_clientsession_with_ssl_and_cookies(self):
        """Test create clientsession with ssl."""
        def _async_helper():
            return client.async_create_clientsession(
                self.hass,
                cookies={'bla': True}
            )

        session = run_callback_threadsafe(
            self.hass.loop,
            _async_helper,
        ).result()

        assert isinstance(
            session, aiohttp.ClientSession)
        assert isinstance(
            self.hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)

    def test_create_clientsession_without_ssl_and_cookies(self):
        """Test create clientsession without ssl."""
        def _async_helper():
            return client.async_create_clientsession(
                self.hass,
                False,
                cookies={'bla': True}
            )

        session = run_callback_threadsafe(
            self.hass.loop,
            _async_helper,
        ).result()

        assert isinstance(
            session, aiohttp.ClientSession)
        assert isinstance(
            self.hass.data[client.DATA_CONNECTOR_NOTVERIFY],
            aiohttp.TCPConnector)
