"""Test the aiohttp client helper."""
import asyncio

import aiohttp
import pytest

from homeassistant.core import EVENT_HOMEASSISTANT_CLOSE
import homeassistant.helpers.aiohttp_client as client
from homeassistant.setup import async_setup_component

from tests.async_mock import Mock, patch


@pytest.fixture(name="camera_client")
def camera_client_fixture(hass, hass_client):
    """Fixture to fetch camera streams."""
    assert hass.loop.run_until_complete(
        async_setup_component(
            hass,
            "camera",
            {
                "camera": {
                    "name": "config_test",
                    "platform": "mjpeg",
                    "mjpeg_url": "http://example.com/mjpeg_stream",
                }
            },
        )
    )
    hass.loop.run_until_complete(hass.async_block_till_done())

    yield hass.loop.run_until_complete(hass_client())


async def test_get_clientsession_with_ssl(hass):
    """Test init clientsession with ssl."""
    client.async_get_clientsession(hass)

    assert isinstance(hass.data[client.DATA_CLIENTSESSION], aiohttp.ClientSession)
    assert isinstance(hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)


async def test_get_clientsession_without_ssl(hass):
    """Test init clientsession without ssl."""
    client.async_get_clientsession(hass, verify_ssl=False)

    assert isinstance(
        hass.data[client.DATA_CLIENTSESSION_NOTVERIFY], aiohttp.ClientSession
    )
    assert isinstance(hass.data[client.DATA_CONNECTOR_NOTVERIFY], aiohttp.TCPConnector)


async def test_create_clientsession_with_ssl_and_cookies(hass):
    """Test create clientsession with ssl."""
    session = client.async_create_clientsession(hass, cookies={"bla": True})
    assert isinstance(session, aiohttp.ClientSession)
    assert isinstance(hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)


async def test_create_clientsession_without_ssl_and_cookies(hass):
    """Test create clientsession without ssl."""
    session = client.async_create_clientsession(hass, False, cookies={"bla": True})
    assert isinstance(session, aiohttp.ClientSession)
    assert isinstance(hass.data[client.DATA_CONNECTOR_NOTVERIFY], aiohttp.TCPConnector)


async def test_get_clientsession_cleanup(hass):
    """Test init clientsession with ssl."""
    client.async_get_clientsession(hass)

    assert isinstance(hass.data[client.DATA_CLIENTSESSION], aiohttp.ClientSession)
    assert isinstance(hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_CLIENTSESSION].closed
    assert hass.data[client.DATA_CONNECTOR].closed


async def test_get_clientsession_cleanup_without_ssl(hass):
    """Test init clientsession with ssl."""
    client.async_get_clientsession(hass, verify_ssl=False)

    assert isinstance(
        hass.data[client.DATA_CLIENTSESSION_NOTVERIFY], aiohttp.ClientSession
    )
    assert isinstance(hass.data[client.DATA_CONNECTOR_NOTVERIFY], aiohttp.TCPConnector)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert hass.data[client.DATA_CLIENTSESSION_NOTVERIFY].closed
    assert hass.data[client.DATA_CONNECTOR_NOTVERIFY].closed


async def test_get_clientsession_patched_close(hass):
    """Test closing clientsession does not work."""
    with patch("aiohttp.ClientSession.close") as mock_close:
        session = client.async_get_clientsession(hass)

        assert isinstance(hass.data[client.DATA_CLIENTSESSION], aiohttp.ClientSession)
        assert isinstance(hass.data[client.DATA_CONNECTOR], aiohttp.TCPConnector)

        with pytest.raises(RuntimeError):
            await session.close()

        assert mock_close.call_count == 0


async def test_warning_close_session_integration(hass, caplog):
    """Test log warning message when closing the session from integration context."""
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/homeassistant/components/hue/light.py",
                lineno="23",
                line="await session.close()",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        session = client.async_get_clientsession(hass)
        await session.close()
    assert (
        "Detected integration that closes the Home Assistant aiohttp session. "
        "Please report issue for hue using this method at "
        "homeassistant/components/hue/light.py, line 23: await session.close()"
    ) in caplog.text


async def test_warning_close_session_custom(hass, caplog):
    """Test log warning message when closing the session from custom context."""
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            Mock(
                filename="/home/paulus/config/custom_components/hue/light.py",
                lineno="23",
                line="await session.close()",
            ),
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        session = client.async_get_clientsession(hass)
        await session.close()
    assert (
        "Detected integration that closes the Home Assistant aiohttp session. "
        "Please report issue to the custom component author for hue using this method at "
        "custom_components/hue/light.py, line 23: await session.close()" in caplog.text
    )


async def test_async_aiohttp_proxy_stream(aioclient_mock, camera_client):
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", content=b"Frame1Frame2Frame3")

    resp = await camera_client.get("/api/camera_proxy_stream/camera.config_test")

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "Frame1Frame2Frame3"


async def test_async_aiohttp_proxy_stream_timeout(aioclient_mock, camera_client):
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", exc=asyncio.TimeoutError())

    resp = await camera_client.get("/api/camera_proxy_stream/camera.config_test")
    assert resp.status == 504


async def test_async_aiohttp_proxy_stream_client_err(aioclient_mock, camera_client):
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", exc=aiohttp.ClientError())

    resp = await camera_client.get("/api/camera_proxy_stream/camera.config_test")
    assert resp.status == 502
