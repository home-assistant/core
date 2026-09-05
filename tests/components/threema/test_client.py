"""Unit tests for the Threema Gateway API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import nacl.public
import pytest

from homeassistant.components.threema.client import (
    ThreemaAPIClient,
    ThreemaAuthError,
    ThreemaConnectionError,
    ThreemaSendError,
    generate_key_pair,
)
from homeassistant.core import HomeAssistant

from .conftest import MOCK_API_SECRET, MOCK_GATEWAY_ID


def _make_resp(status: int = 200, text: str = "OK") -> MagicMock:
    """Create a mock aiohttp response."""
    resp = MagicMock()
    resp.status = status
    resp.ok = status < 400
    resp.text = AsyncMock(return_value=text)
    return resp


def _make_session(
    get_resp: MagicMock | None = None,
    post_resp: MagicMock | None = None,
) -> MagicMock:
    """Create a mock aiohttp client session."""
    session = MagicMock()
    session.get = AsyncMock(return_value=get_resp)
    session.post = AsyncMock(return_value=post_resp)
    return session


def _patch_session(session: MagicMock):
    """Return a context manager that patches async_get_clientsession."""
    return patch(
        "homeassistant.components.threema.client.async_get_clientsession",
        return_value=session,
    )


# ── validate_credentials ─────────────────────────────────────────────────────


async def test_validate_credentials_success(hass: HomeAssistant) -> None:
    """Test successful credential validation."""
    session = _make_session(get_resp=_make_resp(200, "100"))
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        await client.validate_credentials()
    session.get.assert_awaited_once()


async def test_validate_credentials_auth_error(hass: HomeAssistant) -> None:
    """Test that 401 raises ThreemaAuthError."""
    session = _make_session(get_resp=_make_resp(401))
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        with pytest.raises(ThreemaAuthError):
            await client.validate_credentials()


async def test_validate_credentials_server_error(hass: HomeAssistant) -> None:
    """Test that non-401 HTTP error raises ThreemaConnectionError."""
    session = _make_session(get_resp=_make_resp(500))
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        with pytest.raises(ThreemaConnectionError):
            await client.validate_credentials()


@pytest.mark.parametrize(
    "side_effect",
    [aiohttp.ClientError("connection reset"), TimeoutError()],
    ids=["client_error", "timeout"],
)
async def test_validate_credentials_connection_error(
    hass: HomeAssistant, side_effect: Exception
) -> None:
    """Test that a connection error or timeout raises ThreemaConnectionError."""
    session = MagicMock()
    session.get = AsyncMock(side_effect=side_effect)
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        with pytest.raises(ThreemaConnectionError):
            await client.validate_credentials()


# ── send_text_message: simple mode ───────────────────────────────────────────


async def test_send_simple_success(hass: HomeAssistant) -> None:
    """Test successful simple message send."""
    session = _make_session(post_resp=_make_resp(200, "msg123"))
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        message_id = await client.send_text_message("ABCD1234", "Hello!")
    assert message_id == "msg123"
    session.post.assert_awaited_once()


async def test_send_simple_auth_error(hass: HomeAssistant) -> None:
    """Test that 401 during simple send raises ThreemaAuthError."""
    session = _make_session(post_resp=_make_resp(401))
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        with pytest.raises(ThreemaAuthError):
            await client.send_text_message("ABCD1234", "Hello!")


async def test_send_simple_server_error(hass: HomeAssistant) -> None:
    """Test that non-401 HTTP error during simple send raises ThreemaSendError."""
    session = _make_session(post_resp=_make_resp(500))
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        with pytest.raises(ThreemaSendError):
            await client.send_text_message("ABCD1234", "Hello!")


@pytest.mark.parametrize(
    "side_effect",
    [aiohttp.ClientError("connection reset"), TimeoutError()],
    ids=["client_error", "timeout"],
)
async def test_send_simple_connection_error(
    hass: HomeAssistant, side_effect: Exception
) -> None:
    """Test that a connection error or timeout during simple send raises ThreemaSendError."""
    session = MagicMock()
    session.post = AsyncMock(side_effect=side_effect)
    with _patch_session(session):
        client = ThreemaAPIClient(hass, MOCK_GATEWAY_ID, MOCK_API_SECRET)
        with pytest.raises(ThreemaSendError):
            await client.send_text_message("ABCD1234", "Hello!")


# ── send_text_message: E2E mode ───────────────────────────────────────────────


def _e2e_keys() -> tuple[str, nacl.public.PrivateKey]:
    """Return (sender_private_hex, recipient_private_key) for E2E tests."""
    sender = nacl.public.PrivateKey.generate()
    recipient = nacl.public.PrivateKey.generate()
    return bytes(sender).hex(), recipient


async def test_send_e2e_success(hass: HomeAssistant) -> None:
    """Test successful E2E encrypted message send."""
    sender_hex, recipient_priv = _e2e_keys()
    pub_hex = bytes(recipient_priv.public_key).hex()

    session = MagicMock()
    session.get = AsyncMock(return_value=_make_resp(200, pub_hex))
    session.post = AsyncMock(return_value=_make_resp(200, "msg456"))

    with _patch_session(session):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=sender_hex
        )
        message_id = await client.send_text_message("ABCD1234", "Hello E2E!")

    assert message_id == "msg456"
    session.get.assert_awaited_once()
    session.post.assert_awaited_once()


async def test_send_e2e_pubkey_not_found(hass: HomeAssistant) -> None:
    """Test that a 404 fetching pubkey raises ThreemaSendError."""
    sender_hex, _ = _e2e_keys()
    session = MagicMock()
    session.get = AsyncMock(return_value=_make_resp(404))

    with _patch_session(session):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=sender_hex
        )
        with pytest.raises(ThreemaSendError):
            await client.send_text_message("ABCD1234", "Hello E2E!")


async def test_send_e2e_pubkey_auth_error(hass: HomeAssistant) -> None:
    """Test that 401 fetching pubkey raises ThreemaAuthError."""
    sender_hex, _ = _e2e_keys()
    session = MagicMock()
    session.get = AsyncMock(return_value=_make_resp(401))

    with _patch_session(session):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=sender_hex
        )
        with pytest.raises(ThreemaAuthError):
            await client.send_text_message("ABCD1234", "Hello E2E!")


async def test_send_e2e_pubkey_malformed(hass: HomeAssistant) -> None:
    """Test that a malformed pubkey response raises ThreemaSendError."""
    sender_hex, _ = _e2e_keys()
    session = MagicMock()
    session.get = AsyncMock(return_value=_make_resp(200, "not-hex-and-wrong-length"))

    with _patch_session(session):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=sender_hex
        )
        with pytest.raises(ThreemaSendError):
            await client.send_text_message("ABCD1234", "Hello E2E!")


@pytest.mark.parametrize(
    "side_effect",
    [aiohttp.ClientError("connection reset"), TimeoutError()],
    ids=["client_error", "timeout"],
)
async def test_send_e2e_pubkey_connection_error(
    hass: HomeAssistant, side_effect: Exception
) -> None:
    """Test that a connection error or timeout fetching pubkey raises ThreemaSendError."""
    sender_hex, _ = _e2e_keys()
    session = MagicMock()
    session.get = AsyncMock(side_effect=side_effect)

    with _patch_session(session):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=sender_hex
        )
        with pytest.raises(ThreemaSendError):
            await client.send_text_message("ABCD1234", "Hello E2E!")


@pytest.mark.parametrize(
    "side_effect",
    [aiohttp.ClientError("connection reset"), TimeoutError()],
    ids=["client_error", "timeout"],
)
async def test_send_e2e_post_connection_error(
    hass: HomeAssistant, side_effect: Exception
) -> None:
    """Test that a connection error or timeout on POST raises ThreemaSendError."""
    sender_hex, recipient_priv = _e2e_keys()
    pub_hex = bytes(recipient_priv.public_key).hex()

    session = MagicMock()
    session.get = AsyncMock(return_value=_make_resp(200, pub_hex))
    session.post = AsyncMock(side_effect=side_effect)

    with _patch_session(session):
        client = ThreemaAPIClient(
            hass, MOCK_GATEWAY_ID, MOCK_API_SECRET, private_key=sender_hex
        )
        with pytest.raises(ThreemaSendError):
            await client.send_text_message("ABCD1234", "Hello E2E!")


# ── generate_key_pair ─────────────────────────────────────────────────────────


def test_generate_key_pair() -> None:
    """Test that generate_key_pair returns a consistent hex-encoded key pair."""
    private_hex, public_hex = generate_key_pair()

    assert len(private_hex) == 64
    assert len(public_hex) == 64

    # Should parse as valid hex
    private_bytes = bytes.fromhex(private_hex)
    public_bytes = bytes.fromhex(public_hex)

    # Public key must be derivable from private key
    private_key = nacl.public.PrivateKey(private_bytes)
    assert bytes(private_key.public_key) == public_bytes
