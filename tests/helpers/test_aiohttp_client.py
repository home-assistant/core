"""Test the aiohttp client helper."""

from unittest.mock import Mock, patch

import aiohttp
import pytest

from homeassistant.components.mjpeg.const import (
    CONF_MJPEG_URL,
    CONF_STILL_IMAGE_URL,
    DOMAIN as MJPEG_DOMAIN,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import EVENT_HOMEASSISTANT_CLOSE, HomeAssistant
import homeassistant.helpers.aiohttp_client as client
from homeassistant.util.color import RGBColor

from tests.common import (
    MockConfigEntry,
    MockModule,
    extract_stack_to_frame,
    mock_integration,
)
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(name="camera_client")
def camera_client_fixture(hass, hass_client):
    """Fixture to fetch camera streams."""
    mock_config_entry = MockConfigEntry(
        title="MJPEG Camera",
        domain=MJPEG_DOMAIN,
        options={
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_MJPEG_URL: "http://example.com/mjpeg_stream",
            CONF_PASSWORD: None,
            CONF_STILL_IMAGE_URL: None,
            CONF_USERNAME: None,
            CONF_VERIFY_SSL: True,
        },
    )
    mock_config_entry.add_to_hass(hass)
    hass.loop.run_until_complete(
        hass.config_entries.async_setup(mock_config_entry.entry_id)
    )
    hass.loop.run_until_complete(hass.async_block_till_done())

    return hass.loop.run_until_complete(hass_client())


async def test_get_clientsession_with_ssl(hass: HomeAssistant) -> None:
    """Test init clientsession with ssl."""
    client.async_get_clientsession(hass)
    verify_ssl = True
    family = 0

    client_session = hass.data[client.DATA_CLIENTSESSION][(verify_ssl, family)]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family)]
    assert isinstance(connector, aiohttp.TCPConnector)


async def test_get_clientsession_without_ssl(hass: HomeAssistant) -> None:
    """Test init clientsession without ssl."""
    client.async_get_clientsession(hass, verify_ssl=False)
    verify_ssl = False
    family = 0

    client_session = hass.data[client.DATA_CLIENTSESSION][(verify_ssl, family)]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family)]
    assert isinstance(connector, aiohttp.TCPConnector)


@pytest.mark.parametrize(
    ("verify_ssl", "expected_family"),
    [(True, 0), (False, 0), (True, 4), (False, 4), (True, 6), (False, 6)],
)
async def test_get_clientsession(
    hass: HomeAssistant, verify_ssl: bool, expected_family: int
) -> None:
    """Test init clientsession combinations."""
    client.async_get_clientsession(hass, verify_ssl=verify_ssl, family=expected_family)
    client_session = hass.data[client.DATA_CLIENTSESSION][(verify_ssl, expected_family)]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, expected_family)]
    assert isinstance(connector, aiohttp.TCPConnector)


async def test_create_clientsession_with_ssl_and_cookies(hass: HomeAssistant) -> None:
    """Test create clientsession with ssl."""
    session = client.async_create_clientsession(hass, cookies={"bla": True})
    assert isinstance(session, aiohttp.ClientSession)

    verify_ssl = True
    family = 0

    assert client.DATA_CLIENTSESSION not in hass.data
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family)]
    assert isinstance(connector, aiohttp.TCPConnector)


async def test_create_clientsession_without_ssl_and_cookies(
    hass: HomeAssistant,
) -> None:
    """Test create clientsession without ssl."""
    session = client.async_create_clientsession(hass, False, cookies={"bla": True})
    assert isinstance(session, aiohttp.ClientSession)

    verify_ssl = False
    family = 0

    assert client.DATA_CLIENTSESSION not in hass.data
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, family)]
    assert isinstance(connector, aiohttp.TCPConnector)


@pytest.mark.parametrize(
    ("verify_ssl", "expected_family"),
    [(True, 0), (False, 0), (True, 4), (False, 4), (True, 6), (False, 6)],
)
async def test_get_clientsession_cleanup(
    hass: HomeAssistant, verify_ssl: bool, expected_family: int
) -> None:
    """Test init clientsession cleanup."""
    client.async_get_clientsession(hass, verify_ssl=verify_ssl, family=expected_family)

    client_session = hass.data[client.DATA_CLIENTSESSION][(verify_ssl, expected_family)]
    assert isinstance(client_session, aiohttp.ClientSession)
    connector = hass.data[client.DATA_CONNECTOR][(verify_ssl, expected_family)]
    assert isinstance(connector, aiohttp.TCPConnector)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()

    assert client_session.closed
    assert connector.closed


async def test_get_clientsession_patched_close(hass: HomeAssistant) -> None:
    """Test closing clientsession does not work."""

    verify_ssl = True
    family = 0

    with patch("aiohttp.ClientSession.close") as mock_close:
        session = client.async_get_clientsession(hass)

        assert isinstance(
            hass.data[client.DATA_CLIENTSESSION][(verify_ssl, family)],
            aiohttp.ClientSession,
        )
        assert isinstance(
            hass.data[client.DATA_CONNECTOR][(verify_ssl, family)], aiohttp.TCPConnector
        )

        with pytest.raises(RuntimeError):
            await session.close()

        assert mock_close.call_count == 0


@patch("homeassistant.helpers.frame._REPORTED_INTEGRATIONS", set())
async def test_warning_close_session_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test log warning message when closing the session from integration context."""
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
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
                ]
            ),
        ),
    ):
        session = client.async_get_clientsession(hass)
        await session.close()
    assert (
        "Detected that integration 'hue' closes the Home Assistant aiohttp session at "
        "homeassistant/components/hue/light.py, line 23: await session.close(), "
        "please create a bug report at https://github.com/home-assistant/core/issues?"
        "q=is%3Aopen+is%3Aissue+label%3A%22integration%3A+hue%22"
    ) in caplog.text


@patch("homeassistant.helpers.frame._REPORTED_INTEGRATIONS", set())
async def test_warning_close_session_custom(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test log warning message when closing the session from custom context."""
    mock_integration(hass, MockModule("hue"), built_in=False)
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value="await session.close()",
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
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
                ]
            ),
        ),
    ):
        session = client.async_get_clientsession(hass)
        await session.close()
    assert (
        "Detected that custom integration 'hue' closes the Home Assistant aiohttp "
        "session at custom_components/hue/light.py, line 23: await session.close(), "
        "please report it to the author of the 'hue' custom integration"
    ) in caplog.text


async def test_async_aiohttp_proxy_stream(
    aioclient_mock: AiohttpClientMocker, camera_client
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", content=b"Frame1Frame2Frame3")

    resp = await camera_client.get("/api/camera_proxy_stream/camera.mjpeg_camera")

    assert resp.status == 200
    assert aioclient_mock.call_count == 1
    body = await resp.text()
    assert body == "Frame1Frame2Frame3"


async def test_async_aiohttp_proxy_stream_timeout(
    aioclient_mock: AiohttpClientMocker, camera_client
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", exc=TimeoutError())

    resp = await camera_client.get("/api/camera_proxy_stream/camera.mjpeg_camera")
    assert resp.status == 504


async def test_async_aiohttp_proxy_stream_client_err(
    aioclient_mock: AiohttpClientMocker, camera_client
) -> None:
    """Test that it fetches the given url."""
    aioclient_mock.get("http://example.com/mjpeg_stream", exc=aiohttp.ClientError())

    resp = await camera_client.get("/api/camera_proxy_stream/camera.mjpeg_camera")
    assert resp.status == 502


async def test_sending_named_tuple(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test sending a named tuple in json."""
    resp = aioclient_mock.post("http://127.0.0.1/rgb", json={"rgb": RGBColor(4, 3, 2)})
    session = client.async_create_clientsession(hass)
    resp = await session.post("http://127.0.0.1/rgb", json={"rgb": RGBColor(4, 3, 2)})
    assert resp.status == 200
    assert await resp.json() == {"rgb": [4, 3, 2]}
    assert aioclient_mock.mock_calls[0][2]["rgb"] == RGBColor(4, 3, 2)


async def test_client_session_immutable_headers(hass: HomeAssistant) -> None:
    """Test we can't mutate headers."""
    session = client.async_get_clientsession(hass)

    with pytest.raises(TypeError):
        session.headers["user-agent"] = "bla"

    with pytest.raises(AttributeError):
        session.headers.update({"user-agent": "bla"})
