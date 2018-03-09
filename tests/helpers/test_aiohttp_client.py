"""Test the aiohttp client helper."""
import asyncio
import unittest

import aiohttp
import pytest

from homeassistant.core import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.setup import async_setup_component
import homeassistant.helpers.aiohttp_client as client
from homeassistant.util.async import run_callback_threadsafe

from tests.common import get_test_home_assistant


@pytest.fixture
def camera_client(hass, test_client):
    """Fixture to fetch camera streams."""
    assert hass.loop.run_until_complete(async_setup_component(hass, 'camera', {
        'camera': {
            'name': 'config_test',
            'platform': 'mjpeg',
            'mjpeg_url': 'http://example.com/mjpeg_stream',
        }}))

    yield hass.loop.run_until_complete(test_client(hass.http.app))


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

    def test_get_clientsession_cleanup(self):
        """Test init clientsession with ssl."""
        run_callback_threadsafe(self.hass.loop, client.async_get_clientsession,
                                self.hass).result()

        assert isinstance(
            self.hass.data[client.DATA_CLIENTSESSION], aiohttp.ClientSession)
        assert isinstance(
            self.hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)

        self.hass.bus.fire(EVENT_HOMEASSISTANT_CLOSE)
        self.hass.block_till_done()

        assert self.hass.data[client.DATA_CLIENTSESSION].closed
        assert self.hass.data[client.DATA_CONNECTOR].closed

    def test_get_clientsession_cleanup_without_ssl(self):
        """Test init clientsession with ssl."""
        run_callback_threadsafe(self.hass.loop, client.async_get_clientsession,
                                self.hass, False).result()

        assert isinstance(
            self.hass.data[client.DATA_CLIENTSESSION_NOTVERIFY],
            aiohttp.ClientSession)
        assert isinstance(
            self.hass.data[client.DATA_CONNECTOR_NOTVERIFY],
            aiohttp.TCPConnector)

        self.hass.bus.fire(EVENT_HOMEASSISTANT_CLOSE)
        self.hass.block_till_done()

        assert self.hass.data[client.DATA_CLIENTSESSION_NOTVERIFY].closed
        assert self.hass.data[client.DATA_CONNECTOR_NOTVERIFY].closed


@asyncio.coroutine
def test_async_aiohttp_proxy_stream(aioclient_mock, camera_client):
    """Test that it fetches the given url."""
    aioclient_mock.get('http://example.com/mjpeg_stream', content=[
        b'Frame1', b'Frame2', b'Frame3'
    ])

    resp = yield from camera_client.get(
        '/api/camera_proxy_stream/camera.config_test')

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = yield from resp.text()
    assert body == 'Frame3Frame2Frame1'


@asyncio.coroutine
def test_async_aiohttp_proxy_stream_timeout(aioclient_mock, camera_client):
    """Test that it fetches the given url."""
    aioclient_mock.get(
        'http://example.com/mjpeg_stream', exc=asyncio.TimeoutError())

    resp = yield from camera_client.get(
        '/api/camera_proxy_stream/camera.config_test')
    assert resp.status == 504


@asyncio.coroutine
def test_async_aiohttp_proxy_stream_client_err(aioclient_mock, camera_client):
    """Test that it fetches the given url."""
    aioclient_mock.get(
        'http://example.com/mjpeg_stream', exc=aiohttp.ClientError())

    resp = yield from camera_client.get(
        '/api/camera_proxy_stream/camera.config_test')
    assert resp.status == 502
