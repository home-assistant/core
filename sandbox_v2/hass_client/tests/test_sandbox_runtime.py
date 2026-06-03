"""Phase 3 client-side tests for ``hass_client.sandbox``.

The HA Core test suite owns the integration-level coverage (subprocess
spawn, restart budget, multi-group). These tests pin the runtime's
public contract: argparser, the constant the manager scans for, and that
``run()`` exits cleanly when shutdown is requested.
"""

import asyncio

from hass_client.channel import Channel
from hass_client.protocol import MSG_READY
from hass_client.sandbox import SandboxRuntime
from hass_client.sandbox_v2.__main__ import _build_parser
import pytest


async def _noop_channel_factory() -> Channel | None:
    """Channel factory that opens no channel — for in-process shutdown tests."""
    return None


def test_ready_msg_type_is_stable() -> None:
    """The Ready frame type is part of the manager↔runtime protocol."""
    assert MSG_READY == "sandbox_v2/ready"


def test_cli_parser_requires_name_url_and_token() -> None:
    """The CLI parser accepts the manager's argv and defaults log-level."""
    parser = _build_parser()
    args = parser.parse_args(["--name", "built-in", "--url", "ws://x", "--token", "t"])
    assert args.name == "built-in"
    assert args.url == "ws://x"
    assert args.token == "t"
    assert args.log_level == "INFO"

    with pytest.raises(SystemExit):
        parser.parse_args([])


async def test_runtime_starts_in_locked_down_sharing_posture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The sandbox HA sees only its own entities — no subscription to main.

    Phase 20 dropped the unwired ``share_*`` config surface; the
    locked-down posture is now a property of the runtime itself rather
    than a config flag. See ``sandbox_v2/docs/design-share-states.md``
    for the future opt-in design.
    """
    runtime = SandboxRuntime(
        url="ws://x",
        token="t",
        group="custom",
        channel_factory=_noop_channel_factory,
    )

    task = asyncio.create_task(runtime.run())
    loop = asyncio.get_event_loop()
    deadline = loop.time() + 2.0
    while not runtime.started and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert runtime.started

    # The sandbox HA has no subscription to main and no entities yet.
    flow_runner = runtime._flow_runner  # noqa: SLF001
    assert flow_runner is not None
    assert flow_runner.hass.states.async_all() == []

    runtime.request_shutdown()
    exit_code = await asyncio.wait_for(task, timeout=2.0)
    assert exit_code == 0
    capsys.readouterr()  # drain captured output


async def test_runtime_shuts_down_on_request(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``run()`` returns 0 when ``request_shutdown`` is called from outside."""
    runtime = SandboxRuntime(
        url="ws://x",
        token="t",
        group="built-in",
        # Pytest captures stdin/stdout; skip channel setup for this
        # in-process shutdown test (Phase 4 covers the real stdio path
        # via the manager-driven subprocess tests).
        channel_factory=_noop_channel_factory,
    )

    task = asyncio.create_task(runtime.run())

    # Spin until the runtime has installed its shutdown event. The marker
    # round-trip is fast — bail after 2s if something is wrong.
    loop = asyncio.get_event_loop()
    deadline = loop.time() + 2.0
    while not runtime.started and loop.time() < deadline:
        await asyncio.sleep(0.01)

    assert runtime.started

    runtime.request_shutdown()
    exit_code = await asyncio.wait_for(task, timeout=2.0)
    assert exit_code == 0

    # With the noop channel factory there is no channel, so no Ready frame
    # is sent and stdout stays clean (the handshake is a channel frame now,
    # not a stdout text marker). Drain captured output regardless.
    capsys.readouterr()
