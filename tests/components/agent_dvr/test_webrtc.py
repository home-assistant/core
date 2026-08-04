"""Unit tests for the reverse-engineered WebRTC client's own logic.

These deliberately don't touch aiortc / a real RTCPeerConnection — the
handshake and message protocol itself was reverse-engineered from Agent
DVR's own frontend bundle and verified live against a production server
(see webrtc.py's module docstring). What's tested here is the connection
pool's reuse/invalidation behavior and the chunked message framing/
reassembly logic, since both are easy to silently break in a refactor
and don't need a live server to verify.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.agent_dvr.webrtc import (
    AgentDVRWebRTCError,
    AgentDVRWebRTCPool,
    AgentDVRWebRTCSession,
)


async def test_pool_reuses_session_across_calls() -> None:
    """Test the pool only connects once for multiple run() calls."""
    session = AsyncMock()
    factory = MagicMock(return_value=session)
    pool = AgentDVRWebRTCPool(factory)

    await pool.run(AsyncMock(return_value=None))
    await pool.run(AsyncMock(return_value=None))

    factory.assert_called_once()
    session.connect.assert_awaited_once()
    await pool.close()


async def test_pool_drops_session_on_error() -> None:
    """Test a failed call closes the session so the next run() reconnects."""
    sessions = [AsyncMock(), AsyncMock()]
    factory = MagicMock(side_effect=sessions)
    pool = AgentDVRWebRTCPool(factory)

    async def _fail(_session):
        raise AgentDVRWebRTCError("boom")

    with pytest.raises(AgentDVRWebRTCError):
        await pool.run(_fail)

    sessions[0].close.assert_awaited_once()

    await pool.run(AsyncMock(return_value=None))
    assert factory.call_count == 2
    sessions[1].connect.assert_awaited_once()
    await pool.close()


async def test_pool_idle_timeout_closes_session() -> None:
    """Test the pool closes an unused session after IDLE_TIMEOUT."""
    session = AsyncMock()
    pool = AgentDVRWebRTCPool(MagicMock(return_value=session))
    pool.IDLE_TIMEOUT = 0

    await pool.run(AsyncMock(return_value=None))
    # Let the idle-close task (scheduled for 0s) actually run.
    await asyncio.sleep(0.05)

    session.close.assert_awaited_once()


def test_channel_message_reassembly() -> None:
    """Test the "<P|F><ident>_<chunk>" framing used for outgoing/incoming data."""
    fake_channel = MagicMock()
    session = AgentDVRWebRTCSession.__new__(AgentDVRWebRTCSession)
    session._channel = fake_channel
    session._recv_buffers = {}
    session._pending = {}

    fut = asyncio.get_event_loop().create_future()
    session._pending["abc"] = fut

    session._on_channel_message("Pabc_hello ")
    assert not fut.done()
    session._on_channel_message("Pabc_wor")
    session._on_channel_message("Fabc_ld")

    assert fut.done()
    assert fut.result() == "hello world"
    assert "abc" not in session._recv_buffers
