"""The tests for the hassio component."""
from http import HTTPStatus
from unittest.mock import patch

from aiohttp import StreamReader
import pytest

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
def mock_not_onboarded():
    """Mock that we're not onboarded."""
    with patch(
        "homeassistant.components.hassio.http.async_is_onboarded", return_value=False
    ):
        yield


@pytest.fixture
def hassio_user_client(hassio_client, hass_admin_user):
    """Return a Hass.io HTTP client tied to a non-admin user."""
    hass_admin_user.groups = []
    return hassio_client


@pytest.mark.parametrize(
    "path",
    [
        "app/entrypoint.js",
        "addons/bl_b392/logo",
        "addons/bl_b392/icon",
    ],
)
async def test_forward_request_onboarded_user_get(
    hassio_user_client, aioclient_mock: AiohttpClientMocker, path: str
) -> None:
    """Test fetching normal path."""
    aioclient_mock.get(f"http://127.0.0.1/{path}", text="response")

    resp = await hassio_user_client.get(f"/api/hassio/{path}")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    # We only expect a single header.
    assert aioclient_mock.mock_calls[0][3] == {"X-Hass-Source": "core.http"}


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "RANDOM"])
async def test_forward_request_onboarded_user_unallowed_methods(
    hassio_user_client, aioclient_mock: AiohttpClientMocker, method: str
) -> None:
    """Test fetching normal path."""
    resp = await hassio_user_client.post("/api/hassio/app/entrypoint.js")

    # Check we got right response
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED

    # Check we did not forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    ("bad_path", "expected_status"),
    [
        # Caught by bullshit filter
        ("app/%252E./entrypoint.js", HTTPStatus.BAD_REQUEST),
        # The .. is processed, making it an unauthenticated path
        ("app/../entrypoint.js", HTTPStatus.UNAUTHORIZED),
        ("app/%2E%2E/entrypoint.js", HTTPStatus.UNAUTHORIZED),
        # Unauthenticated path
        ("supervisor/info", HTTPStatus.UNAUTHORIZED),
        ("supervisor/logs", HTTPStatus.UNAUTHORIZED),
        ("addons/bl_b392/logs", HTTPStatus.UNAUTHORIZED),
    ],
)
async def test_forward_request_onboarded_user_unallowed_paths(
    hassio_user_client,
    aioclient_mock: AiohttpClientMocker,
    bad_path: str,
    expected_status: int,
) -> None:
    """Test fetching normal path."""
    resp = await hassio_user_client.get(f"/api/hassio/{bad_path}")

    # Check we got right response
    assert resp.status == expected_status
    # Check we didn't forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    "path",
    [
        "app/entrypoint.js",
        "addons/bl_b392/logo",
        "addons/bl_b392/icon",
    ],
)
async def test_forward_request_onboarded_noauth_get(
    hassio_noauth_client, aioclient_mock: AiohttpClientMocker, path: str
) -> None:
    """Test fetching normal path."""
    aioclient_mock.get(f"http://127.0.0.1/{path}", text="response")

    resp = await hassio_noauth_client.get(f"/api/hassio/{path}")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    # We only expect a single header.
    assert aioclient_mock.mock_calls[0][3] == {"X-Hass-Source": "core.http"}


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "RANDOM"])
async def test_forward_request_onboarded_noauth_unallowed_methods(
    hassio_noauth_client, aioclient_mock: AiohttpClientMocker, method: str
) -> None:
    """Test fetching normal path."""
    resp = await hassio_noauth_client.post("/api/hassio/app/entrypoint.js")

    # Check we got right response
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED

    # Check we did not forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    ("bad_path", "expected_status"),
    [
        # Caught by bullshit filter
        ("app/%252E./entrypoint.js", HTTPStatus.BAD_REQUEST),
        # The .. is processed, making it an unauthenticated path
        ("app/../entrypoint.js", HTTPStatus.UNAUTHORIZED),
        ("app/%2E%2E/entrypoint.js", HTTPStatus.UNAUTHORIZED),
        # Unauthenticated path
        ("supervisor/info", HTTPStatus.UNAUTHORIZED),
        ("supervisor/logs", HTTPStatus.UNAUTHORIZED),
        ("addons/bl_b392/logs", HTTPStatus.UNAUTHORIZED),
    ],
)
async def test_forward_request_onboarded_noauth_unallowed_paths(
    hassio_noauth_client,
    aioclient_mock: AiohttpClientMocker,
    bad_path: str,
    expected_status: int,
) -> None:
    """Test fetching normal path."""
    resp = await hassio_noauth_client.get(f"/api/hassio/{bad_path}")

    # Check we got right response
    assert resp.status == expected_status
    # Check we didn't forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    ("path", "authenticated"),
    [
        ("app/entrypoint.js", False),
        ("addons/bl_b392/logo", False),
        ("addons/bl_b392/icon", False),
        ("backups/1234abcd/info", True),
    ],
)
async def test_forward_request_not_onboarded_get(
    hassio_noauth_client,
    aioclient_mock: AiohttpClientMocker,
    path: str,
    authenticated: bool,
    mock_not_onboarded,
) -> None:
    """Test fetching normal path."""
    aioclient_mock.get(f"http://127.0.0.1/{path}", text="response")

    resp = await hassio_noauth_client.get(f"/api/hassio/{path}")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    expected_headers = {
        "X-Hass-Source": "core.http",
    }
    if authenticated:
        expected_headers["Authorization"] = "Bearer 123456"

    assert aioclient_mock.mock_calls[0][3] == expected_headers


@pytest.mark.parametrize(
    "path",
    [
        "backups/new/upload",
        "backups/1234abcd/restore/full",
        "backups/1234abcd/restore/partial",
    ],
)
async def test_forward_request_not_onboarded_post(
    hassio_noauth_client,
    aioclient_mock: AiohttpClientMocker,
    path: str,
    mock_not_onboarded,
) -> None:
    """Test fetching normal path."""
    aioclient_mock.get(f"http://127.0.0.1/{path}", text="response")

    resp = await hassio_noauth_client.get(f"/api/hassio/{path}")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    # We only expect a single header.
    assert aioclient_mock.mock_calls[0][3] == {
        "X-Hass-Source": "core.http",
        "Authorization": "Bearer 123456",
    }


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "RANDOM"])
async def test_forward_request_not_onboarded_unallowed_methods(
    hassio_noauth_client, aioclient_mock: AiohttpClientMocker, method: str
) -> None:
    """Test fetching normal path."""
    resp = await hassio_noauth_client.post("/api/hassio/app/entrypoint.js")

    # Check we got right response
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED

    # Check we did not forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    ("bad_path", "expected_status"),
    [
        # Caught by bullshit filter
        ("app/%252E./entrypoint.js", HTTPStatus.BAD_REQUEST),
        # The .. is processed, making it an unauthenticated path
        ("app/../entrypoint.js", HTTPStatus.UNAUTHORIZED),
        ("app/%2E%2E/entrypoint.js", HTTPStatus.UNAUTHORIZED),
        # Unauthenticated path
        ("supervisor/info", HTTPStatus.UNAUTHORIZED),
        ("supervisor/logs", HTTPStatus.UNAUTHORIZED),
        ("addons/bl_b392/logs", HTTPStatus.UNAUTHORIZED),
    ],
)
async def test_forward_request_not_onboarded_unallowed_paths(
    hassio_noauth_client,
    aioclient_mock: AiohttpClientMocker,
    bad_path: str,
    expected_status: int,
    mock_not_onboarded,
) -> None:
    """Test fetching normal path."""
    resp = await hassio_noauth_client.get(f"/api/hassio/{bad_path}")

    # Check we got right response
    assert resp.status == expected_status
    # Check we didn't forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    ("path", "authenticated"),
    [
        ("app/entrypoint.js", False),
        ("addons/bl_b392/logo", False),
        ("addons/bl_b392/icon", False),
        ("backups/1234abcd/info", True),
        ("supervisor/logs", True),
        ("addons/bl_b392/logs", True),
        ("addons/bl_b392/changelog", True),
        ("addons/bl_b392/documentation", True),
    ],
)
async def test_forward_request_admin_get(
    hassio_client,
    aioclient_mock: AiohttpClientMocker,
    path: str,
    authenticated: bool,
) -> None:
    """Test fetching normal path."""
    aioclient_mock.get(f"http://127.0.0.1/{path}", text="response")

    resp = await hassio_client.get(f"/api/hassio/{path}")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    expected_headers = {
        "X-Hass-Source": "core.http",
    }
    if authenticated:
        expected_headers["Authorization"] = "Bearer 123456"

    assert aioclient_mock.mock_calls[0][3] == expected_headers


@pytest.mark.parametrize(
    "path",
    [
        "backups/new/upload",
        "backups/1234abcd/restore/full",
        "backups/1234abcd/restore/partial",
    ],
)
async def test_forward_request_admin_post(
    hassio_client,
    aioclient_mock: AiohttpClientMocker,
    path: str,
) -> None:
    """Test fetching normal path."""
    aioclient_mock.get(f"http://127.0.0.1/{path}", text="response")

    resp = await hassio_client.get(f"/api/hassio/{path}")

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "response"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    # We only expect a single header.
    assert aioclient_mock.mock_calls[0][3] == {
        "X-Hass-Source": "core.http",
        "Authorization": "Bearer 123456",
    }


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "RANDOM"])
async def test_forward_request_admin_unallowed_methods(
    hassio_client, aioclient_mock: AiohttpClientMocker, method: str
) -> None:
    """Test fetching normal path."""
    resp = await hassio_client.post("/api/hassio/app/entrypoint.js")

    # Check we got right response
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED

    # Check we did not forward command
    assert len(aioclient_mock.mock_calls) == 0


@pytest.mark.parametrize(
    ("bad_path", "expected_status"),
    [
        # Caught by bullshit filter
        ("app/%252E./entrypoint.js", HTTPStatus.BAD_REQUEST),
        # The .. is processed, making it an unauthenticated path
        ("app/../entrypoint.js", HTTPStatus.UNAUTHORIZED),
        ("app/%2E%2E/entrypoint.js", HTTPStatus.UNAUTHORIZED),
        # Unauthenticated path
        ("supervisor/info", HTTPStatus.UNAUTHORIZED),
    ],
)
async def test_forward_request_admin_unallowed_paths(
    hassio_client,
    aioclient_mock: AiohttpClientMocker,
    bad_path: str,
    expected_status: int,
) -> None:
    """Test fetching normal path."""
    resp = await hassio_client.get(f"/api/hassio/{bad_path}")

    # Check we got right response
    assert resp.status == expected_status
    # Check we didn't forward command
    assert len(aioclient_mock.mock_calls) == 0


async def test_bad_gateway_when_cannot_find_supervisor(
    hassio_client, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we get a bad gateway error if we can't find supervisor."""
    aioclient_mock.get("http://127.0.0.1/app/entrypoint.js", exc=TimeoutError)

    resp = await hassio_client.get("/api/hassio/app/entrypoint.js")
    assert resp.status == HTTPStatus.BAD_GATEWAY


async def test_backup_upload_headers(
    hassio_client,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    mock_not_onboarded,
) -> None:
    """Test that we forward the full header for backup upload."""
    content_type = "multipart/form-data; boundary='--webkit'"
    aioclient_mock.post("http://127.0.0.1/backups/new/upload")

    resp = await hassio_client.post(
        "/api/hassio/backups/new/upload", headers={"Content-Type": content_type}
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK

    assert len(aioclient_mock.mock_calls) == 1

    req_headers = aioclient_mock.mock_calls[0][-1]
    assert req_headers["Content-Type"] == content_type


async def test_backup_download_headers(
    hassio_client, aioclient_mock: AiohttpClientMocker, mock_not_onboarded
) -> None:
    """Test that we forward the full header for backup download."""
    content_disposition = "attachment; filename=test.tar"
    aioclient_mock.get(
        "http://127.0.0.1/backups/1234abcd/download",
        headers={
            "Content-Length": "50000000",
            "Content-Disposition": content_disposition,
        },
    )

    resp = await hassio_client.get("/api/hassio/backups/1234abcd/download")

    # Check we got right response
    assert resp.status == HTTPStatus.OK

    assert len(aioclient_mock.mock_calls) == 1

    assert resp.headers["Content-Disposition"] == content_disposition


async def test_stream(hassio_client, aioclient_mock: AiohttpClientMocker) -> None:
    """Verify that the request is a stream."""
    content_type = "multipart/form-data; boundary='--webkit'"
    aioclient_mock.post("http://127.0.0.1/backups/new/upload")
    resp = await hassio_client.post(
        "/api/hassio/backups/new/upload", headers={"Content-Type": content_type}
    )
    # Check we got right response
    assert resp.status == HTTPStatus.OK
    assert isinstance(aioclient_mock.mock_calls[-1][2], StreamReader)


async def test_simple_get_no_stream(
    hassio_client, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify that a simple GET request is not a stream."""
    aioclient_mock.get("http://127.0.0.1/app/entrypoint.js")
    resp = await hassio_client.get("/api/hassio/app/entrypoint.js")
    assert resp.status == HTTPStatus.OK
    assert aioclient_mock.mock_calls[-1][2] is None


async def test_entrypoint_cache_control(
    hassio_client, aioclient_mock: AiohttpClientMocker
) -> None:
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
