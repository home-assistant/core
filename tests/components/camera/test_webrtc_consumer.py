"""Test server-side camera WebRTC session ownership."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.camera import Camera, WebRTCAnswer, WebRTCError
from homeassistant.components.camera.webrtc import WebRTCSendMessage
from homeassistant.exceptions import HomeAssistantError


class ConsumerCamera(Camera):
    """A camera opting in to server-side WebRTC consumption."""

    _attr_supports_server_side_webrtc = True

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Return a fake answer without networking."""
        send_message(WebRTCAnswer("private-answer"))


async def test_unsupported_consumer() -> None:
    """Unsupported cameras fail before creating a session."""
    with pytest.raises(HomeAssistantError, match="server-side WebRTC"):
        await Camera().async_create_webrtc_session("private-offer")


async def test_independent_sessions_and_idempotent_close() -> None:
    """Each viewer owns a separate session and closes it once."""
    camera = ConsumerCamera()
    with patch.object(
        camera, "async_close_webrtc_session", new_callable=AsyncMock
    ) as close:
        first = await camera.async_create_webrtc_session("private-offer")
        second = await camera.async_create_webrtc_session("private-offer")
        assert first.session_id != second.session_id
        assert first.answer == "private-answer"
        assert "private-answer" not in repr(first)
        await asyncio.gather(first.async_close(), first.async_close())
        await second.async_close()
    assert close.await_count == 2


async def test_offer_error_closes_session() -> None:
    """A signaling failure still closes its upstream session."""
    camera = ConsumerCamera()

    async def fail(
        offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        send_message(WebRTCError("offer_failed", "private error detail"))

    with (
        patch.object(camera, "async_handle_async_webrtc_offer", side_effect=fail),
        patch.object(
            camera, "async_close_webrtc_session", new_callable=AsyncMock
        ) as close,
        pytest.raises(HomeAssistantError, match="offer_failed"),
    ):
        await camera.async_create_webrtc_session("private-offer")
    close.assert_awaited_once()


async def test_cancelled_offer_closes_session() -> None:
    """Cancellation closes even an offer that was still negotiating."""
    camera = ConsumerCamera()
    started = asyncio.Event()

    async def wait(
        offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        started.set()
        await asyncio.Event().wait()

    with (
        patch.object(camera, "async_handle_async_webrtc_offer", side_effect=wait),
        patch.object(
            camera, "async_close_webrtc_session", new_callable=AsyncMock
        ) as close,
    ):
        task = asyncio.create_task(camera.async_create_webrtc_session("private-offer"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    close.assert_awaited_once()


async def test_missing_answer_times_out_and_closes() -> None:
    """A camera that returns without an answer cannot leave a session pending."""
    camera = ConsumerCamera()
    timeout = asyncio.timeout
    with (
        patch.object(camera, "async_handle_async_webrtc_offer", new_callable=AsyncMock),
        patch.object(
            camera, "async_close_webrtc_session", new_callable=AsyncMock
        ) as close,
        patch(
            "homeassistant.components.camera.webrtc.asyncio.timeout",
            side_effect=lambda seconds: timeout(0),
        ),
        pytest.raises(TimeoutError),
    ):
        await camera.async_create_webrtc_session("private-offer")
    close.assert_awaited_once()
