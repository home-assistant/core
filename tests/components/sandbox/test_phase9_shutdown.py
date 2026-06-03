"""Phase 9 tests for graceful shutdown orchestration.

The main side spawns the real ``python -m hass_client.sandbox``
runtime, calls :meth:`SandboxManager.async_graceful_shutdown_all`, and
asserts the subprocess exits 0 on its own — no SIGTERM required.

The hung-sandbox case uses an in-memory :class:`SandboxProcess` stub:
the real runtime always honours ``sandbox/shutdown``, so to exercise
the SIGTERM escalation we drive the manager's contract directly with a
process whose channel is wired to never reply.
"""

import asyncio
from collections.abc import AsyncIterator
import sys

import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.manager import (
    SandboxConfig,
    SandboxManager,
    SandboxStartError,
)
from homeassistant.core import HomeAssistant

FAST_CONFIG = SandboxConfig(
    restart_limit=2,
    restart_window=30.0,
    restart_backoff=0.05,
    ready_timeout=20.0,
    shutdown_grace=5.0,
)


@pytest.fixture(name="manager")
async def _manager_fixture(hass: HomeAssistant) -> AsyncIterator[SandboxManager]:
    """Manager that spawns the real runtime; cleans up on teardown."""

    def _factory(group: str, url: str) -> list[str]:
        return [
            sys.executable,
            "-m",
            "hass_client.sandbox",
            "--name",
            group,
            "--url",
            url,
            "--token",
            "phase9-test-token",
        ]

    mgr = SandboxManager(hass, command_factory=_factory, config=FAST_CONFIG)
    yield mgr
    await mgr.async_stop_all()


async def test_graceful_shutdown_exits_subprocess_cleanly(
    manager: SandboxManager,
) -> None:
    """``sandbox/shutdown`` makes the real runtime return 0 on its own."""
    sandbox = await manager.ensure_started("built-in")
    assert sandbox.state == "running"
    assert sandbox.pid is not None
    proc = sandbox._process
    assert proc is not None

    await manager.async_graceful_shutdown_all(timeout=10.0)

    # The runtime should have replied to the shutdown call and then
    # exited 0 on its own. Wait briefly for the supervisor to settle.
    await asyncio.wait_for(proc.wait(), timeout=5.0)
    assert proc.returncode == 0

    # async_stop_all is now a no-op — the supervisor has nothing to clean
    # up — but it must not raise.
    await manager.async_stop_all()
    assert sandbox.state == "stopped"


async def test_graceful_shutdown_falls_through_to_sigterm_on_timeout(
    hass: HomeAssistant,
) -> None:
    """A sandbox that ignores ``sandbox/shutdown`` is killed by ``stop()``.

    The stub runtime here sends the Ready frame, then idles forever
    reading from stdin without ever replying. ``async_graceful_shutdown``
    must time out; the follow-up ``async_stop_all`` then escalates to
    SIGTERM / SIGKILL.
    """

    def _hung_factory(group: str, url: str) -> list[str]:
        return [
            sys.executable,
            "-c",
            (
                "import sys, time, struct;"
                "from hass_client._proto import sandbox_pb2 as pb;"
                # Length-prefixed protobuf Ready push frame — the manager's
                # ProtobufCodec decodes this and flips to "running".
                "frame = pb.Frame(id=0, type='sandbox/ready');"
                "frame.request = pb.Ready().SerializeToString();"
                "body = frame.SerializeToString();"
                "sys.stdout.buffer.write(struct.pack('>I', len(body)) + body);"
                "sys.stdout.buffer.flush();"
                # Just sleep — stdin is wired to the manager but we never read.
                "time.sleep(600)"
            ),
        ]

    short = SandboxConfig(
        restart_limit=1,
        restart_window=30.0,
        restart_backoff=0.05,
        ready_timeout=10.0,
        shutdown_grace=2.0,
    )
    mgr = SandboxManager(hass, command_factory=_hung_factory, config=short)
    sandbox = await mgr.ensure_started("built-in")
    assert sandbox.state == "running"
    proc = sandbox._process
    assert proc is not None

    # Graceful shutdown times out — call channel never replies.
    await mgr.async_graceful_shutdown_all(timeout=0.5)
    # Process must still be alive (the stub sleeps).
    assert proc.returncode is None

    # Existing stop() handles SIGTERM (and SIGKILL if needed).
    await mgr.async_stop_all()
    assert proc.returncode is not None
    assert sandbox.state == "stopped"


async def test_graceful_shutdown_on_no_channel_is_noop(
    hass: HomeAssistant,
) -> None:
    """A sandbox without a live channel reports failure and stays up."""

    def _factory(group: str, url: str) -> list[str]:
        # Failing argv — supervisor records a failed attempt then dies.
        return [sys.executable, "-c", "import sys; sys.exit(1)"]

    mgr = SandboxManager(
        hass,
        command_factory=_factory,
        config=SandboxConfig(
            restart_limit=1,
            restart_window=30.0,
            restart_backoff=0.01,
            ready_timeout=2.0,
            shutdown_grace=1.0,
        ),
    )
    # First start will fail — but ensure_started raises only on the
    # final state; the sandbox entry still gets recorded.
    with pytest.raises(SandboxStartError):
        await mgr.ensure_started("built-in")

    # graceful_shutdown_all must be a safe no-op even with failed sandboxes.
    await mgr.async_graceful_shutdown_all(timeout=0.5)
    await mgr.async_stop_all()


async def test_on_shutdown_reply_callback_is_invoked(
    hass: HomeAssistant,
) -> None:
    """The manager invokes ``on_shutdown_reply`` with each runtime's reply.

    Drives the path that the integration's ``_on_stop`` listener uses
    in production: spawn the real runtime, hand the manager a callback
    that records each reply, and assert the call landed exactly once
    per running sandbox. The reply shape is asserted by the
    hass_client-side ``test_shutdown`` suite — here we only pin that
    the callback wiring fires.
    """
    replies: list[tuple[str, pb.ShutdownResult]] = []

    async def _on_shutdown_reply(group: str, reply: pb.ShutdownResult) -> None:
        replies.append((group, reply))

    def _factory(group: str, url: str) -> list[str]:
        return [
            sys.executable,
            "-m",
            "hass_client.sandbox",
            "--name",
            group,
            "--url",
            url,
            "--token",
            "phase9-reply-test",
        ]

    mgr = SandboxManager(
        hass,
        command_factory=_factory,
        config=FAST_CONFIG,
        on_shutdown_reply=_on_shutdown_reply,
    )
    try:
        await mgr.ensure_started("built-in")
        await mgr.async_graceful_shutdown_all(timeout=10.0)
    finally:
        await mgr.async_stop_all()

    assert len(replies) == 1
    group, reply = replies[0]
    assert group == "built-in"
    assert reply.ok is True
    assert reply.unloaded == 0
    # No integration was loaded → no RestoreEntity → no snapshot.
    # proto: optional field unset (was `restore_state is None`).
    assert not reply.HasField("restore_state")
