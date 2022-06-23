"""The tests for the hassio component."""
import asyncio
from http import HTTPStatus

from aiohttp import StreamReader
import pytest

from homeassistant.components.hassio.http import _need_auth


async def test_forward_request(hassio_client, aioclient_mock):
    """Test fetching normal path."""
    aioclient_mock.post("http://127.0.0.1/beer", text="response")

    resp = await hassio_client.post("/api/hassio/beer")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
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
    assert resp.status == HTTPStatus.UNAUTHORIZED


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
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forward_request_no_auth_for_logo(hassio_client, aioclient_mock):
    """Test no auth needed for logo."""
    aioclient_mock.get("http://127.0.0.1/addons/bl_b392/logo", text="response")

    resp = await hassio_client.get("/api/hassio/addons/bl_b392/logo")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forward_request_no_auth_for_icon(hassio_client, aioclient_mock):
    """Test no auth needed for icon."""
    aioclient_mock.get("http://127.0.0.1/addons/bl_b392/icon", text="response")

    resp = await hassio_client.get("/api/hassio/addons/bl_b392/icon")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_forward_log_request(hassio_client, aioclient_mock):
    """Test fetching normal log path doesn't remove ANSI color escape codes."""
    aioclient_mock.get("http://127.0.0.1/beer/logs", text="\033[32mresponse\033[0m")

    resp = await hassio_client.get("/api/hassio/beer/logs")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "\033[32mresponse\033[0m"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1


async def test_bad_gateway_when_cannot_find_supervisor(hassio_client, aioclient_mock):
    """Test we get a bad gateway error if we can't find supervisor."""
    aioclient_mock.get("http://127.0.0.1/addons/test/info", exc=asyncio.TimeoutError)

    resp = await hassio_client.get("/api/hassio/addons/test/info")
    assert resp.status == HTTPStatus.BAD_GATEWAY


async def test_forwarding_user_info(hassio_client, hass_admin_user, aioclient_mock):
    """Test that we forward user info correctly."""
    aioclient_mock.get("http://127.0.0.1/hello")

    resp = await hassio_client.get("/api/hassio/hello")

    # Check we got right response
    assert resp.status == HTTPStatus.OK

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
    assert resp.status == HTTPStatus.OK

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
    assert resp.status == HTTPStatus.OK

    assert len(aioclient_mock.mock_calls) == 1

    assert resp.headers["Content-Disposition"] == content_disposition


def test_need_auth(hass):
    """Test if the requested path needs authentication."""
    assert not _need_auth(hass, "addons/test/logo")
    assert _need_auth(hass, "backups/new/upload")
    assert _need_auth(hass, "supervisor/logs")

    hass.data["onboarding"] = False
    assert not _need_auth(hass, "backups/new/upload")
    assert not _need_auth(hass, "supervisor/logs")


async def test_stream(hassio_client, aioclient_mock):
    """Verify that the request is a stream."""
    aioclient_mock.get("http://127.0.0.1/test")
    await hassio_client.get("/api/hassio/test", data="test")
    assert isinstance(aioclient_mock.mock_calls[-1][2], StreamReader)


async def test_entrypoint_cache_control(hassio_client, aioclient_mock):
    """Test that we return cache control for requests to the entrypoint only."""
    aioclient_mock.get("http://127.0.0.1/app/entrypoint.js")
    aioclient_mock.get("http://127.0.0.1/app/entrypoint.fdhkusd8y43r.js")

    resp1 = await hassio_client.get("/api/hassio/app/entrypoint.js")
    resp2 = await hassio_client.get("/api/hassio/app/entrypoint.fdhkusd8y43r.js")

    # Check we got right response
    assert resp1.status == HTTPStatus.OK
    assert resp2.status == HTTPStatus.OK

    assert len(aioclient_mock.mock_calls) == 2
    assert resp1.headers["Cache-Control"] == "no-store, max-age=0"

    assert "Cache-Control" not in resp2.headers
