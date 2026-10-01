"""Test admission, identity binding and secret handling for remote Shelly sockets."""

import asyncio
import hashlib
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import WSMessage, WSMsgType, web
from aioshelly.json import json_dumps
import pytest
from yarl import URL

from homeassistant.components.shelly.const import (
    CONF_CONNECTION_TYPE,
    CONF_REMOTE_CREDENTIAL,
    CONNECTION_REMOTE_WS,
    DOMAIN,
)
from homeassistant.components.shelly.remote import (
    REMOTE_LOGGERS,
    RemoteConnectionManager,
    ShellyRemoteReceiver,
    validate_external_url,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEVICE_INFO = {
    "id": "shellyplus1-aabbccddeeff",
    "mac": "AABBCCDDEEFF",
    "gen": 2,
    "model": "SNSW-001X16EU",
    "fw_id": "20260901-120000/1.7.1",
    "ver": "1.7.1",
    "auth_en": False,
}


def make_socket(info: dict) -> MagicMock:
    """Create a finite identity response and a server socket."""
    websocket = MagicMock(spec=web.WebSocketResponse)
    websocket.closed = False
    websocket.prepare = AsyncMock()
    websocket.close = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive = AsyncMock(
        return_value=WSMessage(
            WSMsgType.TEXT, json_dumps({"id": 0, "src": info["id"], "result": info}), ""
        )
    )
    return websocket


def make_request(token: str, *, secure: bool = True) -> MagicMock:
    """Create a request carrying a pairing credential."""
    request = MagicMock(spec=web.Request)
    request.secure = secure
    request.headers = {}
    request.query = {"remote_key": token}
    return request


async def test_credential_hash_and_admission(hass: HomeAssistant) -> None:
    """Generate distinct credentials and retain only SHA-256 verifiers."""
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    token = URL(url).query["remote_key"]
    assert len(token) == 43
    assert record.digest == hashlib.sha256(token.encode()).hexdigest()
    assert manager.lookup(token) is record
    assert token not in repr(record)
    assert token not in repr(manager.credentials)
    second, second_url = manager.create_credential(URL("https://ha.example.com"))
    assert second.digest != record.digest
    assert url != second_url
    assert URL(url).scheme == "wss"
    assert URL(url).path == "/api/shelly/remote"


@pytest.mark.parametrize("token", ["", "wrong", "A" * 43, "A" * 5000, "../token"])
async def test_invalid_credential(hass: HomeAssistant, token: str) -> None:
    """Reject unknown credentials before upgrading or allocating an RPC transport."""
    manager = RemoteConnectionManager(hass)
    response = await ShellyRemoteReceiver(manager).get(make_request(token))
    assert response.status == 401
    assert manager.server.connections == {}


@pytest.mark.parametrize(
    "url",
    [
        "http://ha.example.com",
        "ws://ha.example.com",
        "https://localhost",
        "https://192.168.1.2",
        "https://127.0.0.1",
        "https://ha.local",
        "https://user:password@ha.example.com",
        "https://ha.example.com/path",
        "https://ha.example.com?token=secret",
    ],
)
def test_reject_inappropriate_external_url(url: str) -> None:
    """Only a public HTTPS origin can generate a production connection URL."""
    with pytest.raises(ValueError):
        validate_external_url(url)


async def test_expired_and_revoked_credential(hass: HomeAssistant) -> None:
    """Revocation and pairing expiry remove admission immediately."""
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    token = URL(url).query["remote_key"]
    record.expires_at = asyncio.get_running_loop().time() - 1
    assert manager.lookup(token) is None
    record.expires_at = None
    websocket = make_socket(DEVICE_INFO)
    record.websockets.add(websocket)
    await manager.revoke(record.digest)
    assert manager.lookup(token) is None
    websocket.close.assert_awaited_once_with(code=1008)


async def test_restore_bound_verifier(hass: HomeAssistant) -> None:
    """Restore persistent admission from the hash and unique identity alone."""
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AABBCCDDEEFF",
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: record.digest,
        },
    )
    restored = RemoteConnectionManager(hass)
    result = restored.register_entry(entry)
    assert result.device_id == "AABBCCDDEEFF"
    assert result.expires_at is None
    assert restored.lookup(URL(url).query["remote_key"]) is result


async def test_endpoint_requires_tls(hass: HomeAssistant) -> None:
    """A valid credential cannot authorize insecure transport."""
    manager = RemoteConnectionManager(hass)
    _, url = manager.create_credential(URL("https://ha.example.com"))
    response = await ShellyRemoteReceiver(manager).get(
        make_request(URL(url).query["remote_key"], secure=False)
    )
    assert response.status == 403


async def test_verified_identity_binds_credential(hass: HomeAssistant) -> None:
    """GetDeviceInfo is queried before the candidate reaches normal RPC dispatch."""
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    websocket = make_socket(DEVICE_INFO)
    with (
        patch(
            "homeassistant.components.shelly.remote.web.WebSocketResponse",
            return_value=websocket,
        ),
        patch.object(manager.server, "handle_connection", new=AsyncMock()) as handle,
    ):
        response = await ShellyRemoteReceiver(manager).get(
            make_request(URL(url).query["remote_key"])
        )
    assert response is websocket
    assert record.device_id == "AABBCCDDEEFF"
    assert record.ready.is_set()
    websocket.send_json.assert_awaited_once_with(
        {"id": 0, "src": "ha-shelly-identify", "method": "Shelly.GetDeviceInfo"}
    )
    handle.assert_awaited_once_with(websocket, "AABBCCDDEEFF", DEVICE_INFO["id"])


async def test_mismatched_device_is_rejected(hass: HomeAssistant) -> None:
    """A previously bound credential cannot route a different queried MAC."""
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    record.device_id = "112233445566"
    websocket = make_socket(DEVICE_INFO)
    with (
        patch(
            "homeassistant.components.shelly.remote.web.WebSocketResponse",
            return_value=websocket,
        ),
        patch.object(manager.server, "handle_connection", new=AsyncMock()) as handle,
    ):
        await manager.accept(make_request(URL(url).query["remote_key"]), record)
    websocket.close.assert_awaited_once_with(code=1008)
    handle.assert_not_awaited()
    assert record.device_id == "112233445566"


@pytest.mark.parametrize("logger_name", REMOTE_LOGGERS)
async def test_pairing_urls_are_redacted_in_logs(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, logger_name: str
) -> None:
    """Scrub absolute/relative URLs, URL arguments and exception messages."""
    manager = RemoteConnectionManager(hass)
    _, url = manager.create_credential(URL("https://ha.example.com"))
    logger = logging.getLogger(logger_name)
    logger.warning("Request: %s", URL(url))
    logger.warning("Relative request: %s", URL(url).raw_path_qs)
    def fail() -> None:
        raise ValueError(url)

    try:
        fail()
    except ValueError:
        logger.exception("Failure")
    assert URL(url).query["remote_key"] not in caplog.text
    assert url not in caplog.text
    assert "[REDACTED REMOTE URL]" in caplog.text
