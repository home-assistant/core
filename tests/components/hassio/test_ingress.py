"""The tests for the hassio component."""
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from aiohttp.hdrs import X_FORWARDED_FOR, X_FORWARDED_HOST, X_FORWARDED_PROTO
import pytest

from homeassistant.components.hassio.const import X_AUTH_TOKEN

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ping?index=1"),
        ("core", "index.html"),
        ("local", "panel/config"),
        ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", ""),
    ],
)
async def test_ingress_request_get(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.get(
        f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}",
        text="test",
    )

    resp = await hassio_client.get(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ping?index=1"),
        ("core", "index.html"),
        ("local", "panel/config"),
        ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", ""),
    ],
)
async def test_ingress_request_post(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.post(
        f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}",
        text="test",
    )

    resp = await hassio_client.post(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ping?index=1"),
        ("core", "index.html"),
        ("local", "panel/config"),
        ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", ""),
    ],
)
async def test_ingress_request_put(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.put(
        f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}",
        text="test",
    )

    resp = await hassio_client.put(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ping?index=1"),
        ("core", "index.html"),
        ("local", "panel/config"),
        ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", ""),
    ],
)
async def test_ingress_request_delete(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.delete(
        f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}",
        text="test",
    )

    resp = await hassio_client.delete(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ping?index=1"),
        ("core", "index.html"),
        ("local", "panel/config"),
        ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", ""),
    ],
)
async def test_ingress_request_patch(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.patch(
        f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}",
        text="test",
    )

    resp = await hassio_client.patch(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ping?index=1"),
        ("core", "index.html"),
        ("local", "panel/config"),
        ("jk_921", "editor.php?idx=3&ping=5"),
        ("fsadjf10312", ""),
    ],
)
async def test_ingress_request_options(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.options(
        f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}",
        text="test",
    )

    resp = await hassio_client.options(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we got right response
    assert resp.status == HTTPStatus.OK
    body = await resp.text()
    assert body == "test"

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


@pytest.mark.parametrize(
    "build_type",
    [
        ("a3_vl", "test/beer/ws"),
        ("core", "ws.php"),
        ("local", "panel/config/stream"),
        ("jk_921", "hulk"),
        ("demo", "ws/connection?id=9&token=SJAKWS283"),
    ],
)
async def test_ingress_websocket(
    hassio_client, build_type, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test no auth needed for ."""
    aioclient_mock.get(f"http://127.0.0.1/ingress/{build_type[0]}/{build_type[1]}")

    # Ignore error because we can setup a full IO infrastructure
    await hassio_client.ws_connect(
        f"/api/hassio_ingress/{build_type[0]}/{build_type[1]}",
        headers={"X-Test-Header": "beer"},
    )

    # Check we forwarded command
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[-1][3][X_AUTH_TOKEN] == "123456"
    assert (
        aioclient_mock.mock_calls[-1][3]["X-Ingress-Path"]
        == f"/api/hassio_ingress/{build_type[0]}"
    )
    assert aioclient_mock.mock_calls[-1][3]["X-Test-Header"] == "beer"
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_FOR]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_HOST]
    assert aioclient_mock.mock_calls[-1][3][X_FORWARDED_PROTO]


async def test_ingress_missing_peername(
    hassio_client, aioclient_mock: AiohttpClientMocker, caplog: pytest.LogCaptureFixture
) -> None:
    """Test hadnling of missing peername."""
    aioclient_mock.get(
        "http://127.0.0.1/ingress/lorem/ipsum",
        text="test",
    )

    def get_extra_info(_):
        return None

    with patch(
        "aiohttp.web_request.BaseRequest.transport",
        return_value=MagicMock(),
    ) as transport_mock:
        transport_mock.get_extra_info = get_extra_info
        resp = await hassio_client.get(
            "/api/hassio_ingress/lorem/ipsum",
            headers={"X-Test-Header": "beer"},
        )

    assert "Can't set forward_for header, missing peername" in caplog.text

    # Check we got right response
    assert resp.status == HTTPStatus.BAD_REQUEST
