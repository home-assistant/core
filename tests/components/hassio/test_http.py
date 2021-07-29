"""The tests for the hassio component."""
from aiohttp.client import ClientError
from aiohttp.streams import StreamReader
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.hassio.http import _need_auth

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_forward_request(hassio_client, aioclient_mock):
    """Test fetching normal path."""
    aioclient_mock.post("http://127.0.0.1/beer", text="response")

    resp = await hassio_client.post("/api/hassio/beer")

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


@pytest.mark.parametrize(
    "build_type", ["supervisor/info", "homeassistant/update", "host/info"]
)
async def test_auth_required_forward_request(hassio_noauth_client, build_type):
    """Test auth required for normal request."""
    resp = await hassio_noauth_client.post(f"/api/hassio/{build_type}")

    # Check we got right response
    assert resp.status == 401


@pytest.mark.parametrize(
    "build_type",
    [
        "app/index.html",
        "app/hassio-app.html",
        "app/index.html",
        "app/hassio-app.html",
        "app/some-chunk.js",
        "app/app.js",
    ],
)
async def test_forward_request_no_auth_for_panel(
    hassio_client, build_type, aioclient_mock
):
    """Test no auth needed for ."""
    aioclient_mock.get(f"http://127.0.0.1/{build_type}", text="response")

    resp = await hassio_client.get(f"/api/hassio/{build_type}")

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forward_request_no_auth_for_logo(hassio_client, aioclient_mock):
    """Test no auth needed for logo."""
    aioclient_mock.get("http://127.0.0.1/addons/bl_b392/logo", text="response")

    resp = await hassio_client.get("/api/hassio/addons/bl_b392/logo")

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forward_request_no_auth_for_icon(hassio_client, aioclient_mock):
    """Test no auth needed for icon."""
    aioclient_mock.get("http://127.0.0.1/addons/bl_b392/icon", text="response")

    resp = await hassio_client.get("/api/hassio/addons/bl_b392/icon")

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forward_log_request(hassio_client, aioclient_mock):
    """Test fetching normal log path doesn't remove ANSI color escape codes."""
    aioclient_mock.get("http://127.0.0.1/beer/logs", text="\033[32mresponse\033[0m")

    resp = await hassio_client.get("/api/hassio/beer/logs")

    # Check we got right response
    assert resp.status == 200
    body = await resp.text()
    assert body == "\033[32mresponse\033[0m"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forwarding_user_info(hassio_client, hass_admin_user, aioclient_mock):
    """Test that we forward user info correctly."""
    aioclient_mock.get("http://127.0.0.1/hello")

    resp = await hassio_client.get("/api/hassio/hello")

    # Check we got right response
    assert resp.status == 200

    assert len(aioclient_mock.mock_calls) == 1

    req_headers = aioclient_mock.mock_calls[0][-1]
    assert req_headers["X-Hass-User-ID"] == hass_admin_user.id
    assert req_headers["X-Hass-Is-Admin"] == "1"


async def test_backup_upload_headers(hassio_client, aioclient_mock, caplog):
    """Test that we forward the full header for backup upload."""
    content_type = "multipart/form-data; boundary='--webkit'"
    aioclient_mock.get("http://127.0.0.1/backups/new/upload")

    resp = await hassio_client.get(
        "/api/hassio/backups/new/upload", headers={"Content-Type": content_type}
    )

    # Check we got right response
    assert resp.status == 200

    assert len(aioclient_mock.mock_calls) == 1

    req_headers = aioclient_mock.mock_calls[0][-1]
    assert req_headers["Content-Type"] == content_type


async def test_backup_download_headers(hassio_client, aioclient_mock):
    """Test that we forward the full header for backup download."""
    content_disposition = "attachment; filename=test.tar"
    aioclient_mock.get(
        "http://127.0.0.1/backups/slug/download",
        headers={
            "Content-Length": "50000000",
            "Content-Disposition": content_disposition,
        },
    )

    resp = await hassio_client.get("/api/hassio/backups/slug/download")

    # Check we got right response
    assert resp.status == 200

    assert len(aioclient_mock.mock_calls) == 1

    assert resp.headers["Content-Disposition"] == content_disposition


async def test_supervisor_client_error(
    hassio_client: TestClient, aioclient_mock: AiohttpClientMocker
):
    """Test any client error from the supervisor returns a 502."""
    # Create a request that throws a ClientError
    async def raise_client_error(*args):
        raise ClientError()

    aioclient_mock.get(
        "http://127.0.0.1/test/raise/error",
        side_effect=raise_client_error,
    )

    # Verify it returns bad gateway
    resp = await hassio_client.get("/api/hassio/test/raise/error")
    assert resp.status == 502
    assert len(aioclient_mock.mock_calls) == 1


async def test_streamed_requests(
    hassio_client: TestClient, aioclient_mock: AiohttpClientMocker
):
    """Test requests get proxied to the supervisor as a stream."""
    aioclient_mock.get("http://127.0.0.1/test/stream")
    await hassio_client.get("/api/hassio/test/stream", data="Test data")
    assert len(aioclient_mock.mock_calls) == 1

    # Verify the request body is passed as a StreamReader
    assert isinstance(aioclient_mock.mock_calls[0][2], StreamReader)


def test_need_auth(hass):
    """Test if the requested path needs authentication."""
    assert not _need_auth(hass, "addons/test/logo")
    assert _need_auth(hass, "backups/new/upload")
    assert _need_auth(hass, "supervisor/logs")

    hass.data["onboarding"] = False
    assert not _need_auth(hass, "backups/new/upload")
    assert not _need_auth(hass, "supervisor/logs")
