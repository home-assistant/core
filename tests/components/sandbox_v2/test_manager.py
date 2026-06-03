"""Phase 3 tests for the sandbox_v2 lifecycle manager.

These exercise the real subprocess machinery — the runtime entry point at
``python -m hass_client.sandbox_v2`` is spawned for the happy path; the
restart-budget and isolation tests use a stub argv that the manager can
spawn and that fails immediately.
"""

import asyncio
from collections.abc import AsyncIterator
import sys
import time

import pytest

from homeassistant.components.sandbox_v2.manager import (
    SandboxConfig,
    SandboxFailedError,
    SandboxManager,
    SandboxStartError,
)
from homeassistant.core import HomeAssistant

# Tighter timings than production defaults so the test suite stays brisk.
FAST_CONFIG = SandboxConfig(
    restart_limit=3,
    restart_window=60.0,
    restart_backoff=0.05,
    ready_timeout=15.0,
    shutdown_grace=5.0,
)

# Argv stub for "process that exits immediately with status 1". Used by
# tests that exercise the restart budget without going through the real
# runtime.
_FAILING_CMD = [sys.executable, "-c", "import sys; sys.exit(1)"]


@pytest.fixture
async def manager(hass: HomeAssistant) -> AsyncIterator[SandboxManager]:
    """Manager wired with FAST_CONFIG; cleans up every sandbox on teardown."""
    mgr = SandboxManager(hass, config=FAST_CONFIG)
    yield mgr
    await mgr.async_stop_all()


async def test_spawn_and_teardown(manager: SandboxManager) -> None:
    """The manager can spawn the real runtime and tear it down cleanly."""
    sandbox = await manager.ensure_started("built-in")

    assert sandbox.state == "running"
    assert sandbox.group == "built-in"
    pid = sandbox.pid
    assert pid is not None

    # ensure_started is idempotent while running.
    again = await manager.ensure_started("built-in")
    assert again is sandbox
    assert again.pid == pid

    await manager.async_stop("built-in")

    assert sandbox.state == "stopped"
    assert sandbox.pid is None


async def test_crash_restart_budget(hass: HomeAssistant) -> None:
    """A sandbox that crashes 3 times in the window is marked failed."""
    spawn_times: list[float] = []

    def failing_factory(group: str, url: str) -> list[str]:
        spawn_times.append(time.monotonic())
        return _FAILING_CMD

    mgr = SandboxManager(hass, command_factory=failing_factory, config=FAST_CONFIG)

    with pytest.raises(SandboxStartError):
        await mgr.ensure_started("built-in")

    # Exactly `restart_limit` spawn attempts, then mark failed.
    assert len(spawn_times) == FAST_CONFIG.restart_limit
    sandbox = mgr.get("built-in")
    assert sandbox is not None
    assert sandbox.state == "failed"

    # Backoff visible between attempts: at least (limit - 1) * backoff
    # seconds between the first and last spawn.
    minimum = (FAST_CONFIG.restart_limit - 1) * FAST_CONFIG.restart_backoff
    assert spawn_times[-1] - spawn_times[0] >= minimum

    # ensure_started against a failed sandbox surfaces SandboxFailedError
    # instead of silently respawning.
    with pytest.raises(SandboxFailedError):
        await mgr.ensure_started("built-in")

    await mgr.async_stop_all()


async def test_multiple_groups_independent(hass: HomeAssistant) -> None:
    """A failed group does not stop a healthy group from running."""

    def mixed_factory(group: str, url: str) -> list[str]:
        if group == "broken":
            return _FAILING_CMD
        return [
            sys.executable,
            "-m",
            "hass_client.sandbox_v2",
            "--name",
            group,
            "--url",
            url,
            "--token",
            "test-token",
        ]

    mgr = SandboxManager(hass, command_factory=mixed_factory, config=FAST_CONFIG)
    try:
        good = await mgr.ensure_started("built-in")
        assert good.state == "running"
        good_pid = good.pid
        assert good_pid is not None

        with pytest.raises(SandboxStartError):
            await mgr.ensure_started("broken")
        broken = mgr.get("broken")
        assert broken is not None
        assert broken.state == "failed"

        # Give the healthy sandbox a beat to make sure nothing leaked into
        # its lifecycle while the broken one was failing.
        await asyncio.sleep(0.1)
        assert good.state == "running"
        assert good.pid == good_pid

        # A second healthy group runs alongside without interference.
        also_good = await mgr.ensure_started("custom")
        assert also_good.state == "running"
        assert also_good.pid != good_pid
    finally:
        await mgr.async_stop_all()

    assert good.state == "stopped"
    assert mgr.get("custom") is not None
    assert mgr.get("custom").state == "stopped"  # type: ignore[union-attr]
    # Broken sandbox stays in the "failed" bucket — async_stop_all is a
    # no-op for it but must not raise.
    assert mgr.get("broken").state == "failed"  # type: ignore[union-attr]


async def test_default_command_includes_token(
    hass: HomeAssistant,
) -> None:
    """The default command embeds the cached scoped token in argv."""

    async def fake_token(group: str) -> str:
        return f"token-{group}"

    mgr = SandboxManager(hass, token_factory=fake_token)
    # Prime the token cache without actually launching a subprocess.
    mgr._tokens["built-in"] = "token-built-in"

    builtin_argv = mgr._default_command("built-in", "stdio://")
    assert "token-built-in" in builtin_argv
    assert "--name" in builtin_argv
    assert "built-in" in builtin_argv
    assert "stdio://" in builtin_argv


async def test_ensure_started_awaits_token_factory(hass: HomeAssistant) -> None:
    """The token factory is invoked once per group when starting."""
    calls: list[str] = []

    async def fake_token(group: str) -> str:
        calls.append(group)
        return f"token-{group}"

    def quick_command(group: str, url: str) -> list[str]:
        return _FAILING_CMD  # Force a fast failure so the test runs fast.

    mgr = SandboxManager(
        hass,
        command_factory=quick_command,
        token_factory=fake_token,
        config=FAST_CONFIG,
    )

    with pytest.raises(SandboxStartError):
        await mgr.ensure_started("built-in")
    await mgr.async_stop_all()

    # The token factory was awaited (and cached) before the failing spawn.
    assert calls == ["built-in"]
    assert mgr._tokens["built-in"] == "token-built-in"
