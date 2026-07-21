"""Pre-auth pairing protocol for the Poolside controller (plaintext text frames)."""

from base64 import b64decode, b64encode
from dataclasses import dataclass
from typing import Any

import aiohttp


class PairingError(Exception):
    """Base error for pairing failures."""


class PairingRejected(PairingError):
    """The user rejected the pairing request on the controller."""


class PairingTimedOut(PairingError):
    """Nobody approved or rejected the request before the pairing window lapsed."""


class PairingBusy(PairingError):
    """Another pairing is already pending on the controller."""


class PairingInvalid(PairingError):
    """The controller rejected the pairing request as malformed."""


@dataclass
class PairingPending:
    """The controller parked the request and is waiting on user approval."""

    fingerprint: str
    expires_at: str


@dataclass
class PairingApproved:
    """The controller approved this client, pinning its static public key."""

    fingerprint: str
    controller_public_key: bytes
    controller_uuid: str


async def async_request_pairing(
    session: aiohttp.ClientSession,
    host: str,
    port: int,
    name: str,
    public_key: bytes,
) -> tuple[aiohttp.ClientWebSocketResponse, PairingPending | PairingApproved]:
    """Open the pairing socket and send the initial pair_request.

    Returns the open websocket together with either an immediate
    ``PairingApproved`` (already-paired client, socket is already closed) or a
    ``PairingPending`` the caller should display while awaiting
    ``async_await_pairing_result`` on the same (still open) socket.
    """
    ws = await session.ws_connect(f"ws://{host}:{port}/")
    try:
        await ws.send_json(
            {
                "type": "pair_request",
                "name": name,
                "publicKey": b64encode(public_key).decode(),
            }
        )
        message = await _receive_pairing_message(ws)
    except BaseException:
        await ws.close()
        raise

    msg_type = message.get("type")
    if msg_type == "pair_pending":
        return ws, PairingPending(
            fingerprint=message["fingerprint"], expires_at=message["expiresAt"]
        )
    if msg_type == "pair_approved":
        await ws.close()
        return ws, _parse_approved(message)

    await ws.close()
    _raise_for_message(message)
    raise PairingError(f"Unexpected pairing response: {message}")


async def async_await_pairing_result(
    ws: aiohttp.ClientWebSocketResponse,
) -> PairingApproved:
    """Wait for the controller's final pairing decision and close the socket."""
    try:
        message = await _receive_pairing_message(ws)
    finally:
        await ws.close()

    if message.get("type") == "pair_approved":
        return _parse_approved(message)
    _raise_for_message(message)
    raise PairingError(f"Unexpected pairing response: {message}")


def _parse_approved(message: dict[str, Any]) -> PairingApproved:
    return PairingApproved(
        fingerprint=message["fingerprint"],
        controller_public_key=b64decode(message["controllerPublicKey"]),
        controller_uuid=message["controllerUuid"],
    )


def _raise_for_message(message: dict[str, Any]) -> None:
    msg_type = message.get("type")
    if msg_type == "pair_rejected":
        raise PairingRejected
    if msg_type == "pair_timeout":
        raise PairingTimedOut
    if msg_type == "pair_busy":
        raise PairingBusy
    if msg_type == "pair_invalid":
        raise PairingInvalid
    if msg_type == "error":
        raise PairingError(message.get("error", "unknown_error"))


async def _receive_pairing_message(
    ws: aiohttp.ClientWebSocketResponse,
) -> dict[str, Any]:
    """Receive and JSON-decode the next text frame, rejecting anything else."""
    msg = await ws.receive()
    if msg.type is not aiohttp.WSMsgType.TEXT:
        raise PairingError(f"Expected a text frame during pairing, got {msg.type}")
    return msg.json()
