"""The tests for the hassio component."""
import asyncio

import pytest

from tests.async_mock import patch


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


async def test_bad_gateway_when_cannot_find_supervisor(hassio_client):
    """Test we get a bad gateway error if we can't find supervisor."""
    with patch(
        "homeassistant.components.hassio.http.async_timeout.timeout",
        side_effect=asyncio.TimeoutError,
    ):
        resp = await hassio_client.get("/api/hassio/addons/test/info")
    assert resp.status == 502


async def test_forwarding_user_info(hassio_client, hass_admin_user, aioclient_mock):
    """Test that we forward user info correctly."""
    aioclient_mock.get("http://127.0.0.1/hello")

    resp = await hassio_client.get("/api/hassio/hello")

    # Check we got right response
    assert resp.status == 200

    assert len(aioclient_mock.mock_calls) == 1

    req_headers = aioclient_mock.mock_calls[0][-1]
    req_headers["X-Hass-User-ID"] == hass_admin_user.id
    req_headers["X-Hass-Is-Admin"] == "1"


async def test_snapshot_upload_headers(hassio_client, aioclient_mock):
    """Test that we forward the full header for snapshot upload."""
    content_type = "multipart/form-data; boundary='--webkit'"
    aioclient_mock.get("http://127.0.0.1/snapshots/new/upload")

    resp = await hassio_client.get(
        "/api/hassio/snapshots/new/upload", headers={"Content-Type": content_type}
    )

    # Check we got right response
    assert resp.status == 200

    assert len(aioclient_mock.mock_calls) == 1

    req_headers = aioclient_mock.mock_calls[0][-1]
    req_headers["Content-Type"] == content_type
