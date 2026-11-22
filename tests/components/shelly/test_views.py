"""Tests for Shelly views."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientError, ClientPayloadError
from aioshelly.const import MODEL_CAMERA
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator
from yarl import URL

from homeassistant.components.shelly.const import CONF_SLEEP_PERIOD
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_PORT
from homeassistant.core import HomeAssistant

from . import init_integration

PATH = "11111111-1111-1111-1111-111111111111/aaaa1111/MOV_0001.mp4"
DEVICE_URL = f"http://192.168.1.37/storage/{PATH}"
VIDEO = b"0123456789"


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a storage file is streamed from the device."""
    aioclient_mock.get(
        DEVICE_URL,
        content=VIDEO,
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(len(VIDEO)),
            "Accept-Ranges": "bytes",
            "ETag": '"abc"',
            "Cache-Control": "no-cache",
            "Set-Cookie": "session=secret",
        },
    )
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    response = await client.get(
        f"/api/shelly/storage/{entry.entry_id}/{PATH}",
        headers={"If-None-Match": '"xyz"', "Cookie": "a=b"},
    )

    assert response.status == HTTPStatus.OK
    assert await response.read() == VIDEO
    assert response.headers["Content-Type"] == "video/mp4"
    assert response.headers["Content-Length"] == str(len(VIDEO))
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["ETag"] == '"abc"'
    assert response.headers["Cache-Control"] == "no-cache"
    assert "Set-Cookie" not in response.headers
    # The HA access token and cookies must never reach the device.
    assert aioclient_mock.mock_calls[0][3] == {
        "Accept-Encoding": "identity",
        "If-None-Match": '"xyz"',
    }


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_range(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test range requests are forwarded to the device."""
    aioclient_mock.get(
        DEVICE_URL,
        status=HTTPStatus.PARTIAL_CONTENT,
        content=VIDEO[2:5],
        headers={"Content-Type": "video/mp4", "Content-Range": "bytes 2-4/10"},
    )
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    response = await client.get(
        f"/api/shelly/storage/{entry.entry_id}/{PATH}",
        headers={"Range": "bytes=2-4", "If-Range": '"abc"'},
    )

    assert response.status == HTTPStatus.PARTIAL_CONTENT
    assert response.headers["Content-Range"] == "bytes 2-4/10"
    assert await response.read() == VIDEO[2:5]
    assert aioclient_mock.mock_calls[0][3] == {
        "Accept-Encoding": "identity",
        "Range": "bytes=2-4",
        "If-Range": '"abc"',
    }


@pytest.mark.parametrize(
    ("port", "device_url"),
    [
        (80, f"http://192.168.1.37/storage/{PATH}"),
        (8080, f"http://192.168.1.37:8080/storage/{PATH}"),
        (443, f"https://192.168.1.37/storage/{PATH}"),
    ],
)
@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_device_port(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    port: int,
    device_url: str,
) -> None:
    """Test the device is reached on the scheme and port of the entry."""
    aioclient_mock.get(device_url, content=VIDEO)
    entry = await init_integration(
        hass,
        3,
        model=MODEL_CAMERA,
        data={
            CONF_HOST: "192.168.1.37",
            CONF_PORT: port,
            CONF_SLEEP_PERIOD: 0,
            CONF_MODEL: MODEL_CAMERA,
        },
    )
    client = await hass_client()

    response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

    assert response.status == HTTPStatus.OK
    assert await response.read() == VIDEO


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_device_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a device 404 is passed through."""
    aioclient_mock.get(DEVICE_URL, status=HTTPStatus.NOT_FOUND)
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

    assert response.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("exc", [ClientError(), TimeoutError()])
@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_device_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    exc: Exception,
) -> None:
    """Test connection errors to the device return bad gateway."""
    aioclient_mock.get(DEVICE_URL, exc=exc)
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

    assert response.status == HTTPStatus.BAD_GATEWAY


def mock_upstream(
    status: HTTPStatus, headers: dict[str, str], chunks: list[bytes | Exception]
) -> Mock:
    """Return a mock session answering with the given upstream response."""
    content = Mock()
    content.__aiter__ = Mock(return_value=content)
    content.__anext__ = AsyncMock(side_effect=chunks)
    upstream = MagicMock(status=status, headers=headers)
    upstream.content.iter_chunked = Mock(return_value=content)
    session = Mock()
    session.get = AsyncMock(return_value=upstream)
    return session


@pytest.mark.parametrize(
    "headers", [{"Content-Length": str(len(VIDEO))}, {"Content-Type": "video/mp4"}]
)
@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_upstream_drops(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    headers: dict[str, str],
) -> None:
    """Test a failure while streaming aborts the response to the client."""
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    with patch(
        "homeassistant.components.shelly.views.async_get_clientsession",
        return_value=mock_upstream(
            HTTPStatus.OK, headers, [VIDEO[:4], ClientPayloadError()]
        ),
    ):
        response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

        assert response.status == HTTPStatus.OK
        with pytest.raises(ClientPayloadError):
            await response.read()


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_redirect_not_followed(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test a device redirect is passed through and never followed."""
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()
    session = mock_upstream(
        HTTPStatus.FOUND, {"Location": "http://example.com/"}, [StopAsyncIteration()]
    )

    with patch(
        "homeassistant.components.shelly.views.async_get_clientsession",
        return_value=session,
    ):
        response = await client.get(
            f"/api/shelly/storage/{entry.entry_id}/{PATH}", allow_redirects=False
        )

    assert response.status == HTTPStatus.FOUND
    assert "Location" not in response.headers
    session.get.assert_awaited_once()
    assert session.get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("a/..", HTTPStatus.NOT_FOUND),
        ("a/%2e%2e", HTTPStatus.NOT_FOUND),
        ("a/%2E%2E", HTTPStatus.NOT_FOUND),
        ("a/%2e/b", HTTPStatus.NOT_FOUND),
        ("..%5c..%5crpc", HTTPStatus.NOT_FOUND),
        ("..%2f..%2frpc", HTTPStatus.BAD_REQUEST),
        ("%2e%2e/rpc", HTTPStatus.BAD_REQUEST),
        ("%252e%252e/rpc", HTTPStatus.BAD_REQUEST),
        ("a%252fb", HTTPStatus.NOT_FOUND),
        ("a//b", HTTPStatus.NOT_FOUND),
        ("a/b/", HTTPStatus.NOT_FOUND),
        ("@evil.com/b", HTTPStatus.NOT_FOUND),
        ("a%3fx=1", HTTPStatus.NOT_FOUND),
        ("a%23b", HTTPStatus.NOT_FOUND),
        ("a%00b", HTTPStatus.NOT_FOUND),
        ("a:b", HTTPStatus.NOT_FOUND),
    ],
)
@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_path_traversal(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    path: str,
    status: HTTPStatus,
) -> None:
    """Test paths that could leave device storage are rejected."""
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    # Send the path as is, the client would otherwise normalize dot segments.
    response = await client.get(
        URL(f"/api/shelly/storage/{entry.entry_id}/{path}", encoded=True)
    )

    assert response.status == status
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(("gen", "sleep_period"), [(1, 0), (3, 1000)])
@pytest.mark.usefixtures("mock_block_device", "mock_camera_storage")
async def test_storage_proxy_unsupported_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    gen: int,
    sleep_period: int,
) -> None:
    """Test entries without a storage capable device are rejected."""
    entry = await init_integration(hass, gen, sleep_period=sleep_period)
    client = await hass_client()

    response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

    assert response.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_unloaded_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unloaded entries are rejected."""
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    await hass.config_entries.async_unload(entry.entry_id)
    client = await hass_client()

    response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

    assert response.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_unknown_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test unknown entries are rejected."""
    await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client()

    response = await client.get(f"/api/shelly/storage/unknown/{PATH}")

    assert response.status == HTTPStatus.NOT_FOUND
    assert aioclient_mock.call_count == 0


@pytest.mark.usefixtures("mock_camera_storage")
async def test_storage_proxy_requires_auth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the view requires authentication."""
    entry = await init_integration(hass, 3, model=MODEL_CAMERA)
    client = await hass_client_no_auth()

    response = await client.get(f"/api/shelly/storage/{entry.entry_id}/{PATH}")

    assert response.status == HTTPStatus.UNAUTHORIZED
    assert aioclient_mock.call_count == 0
