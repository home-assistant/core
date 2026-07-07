"""Client-side tests for ``hass_client.sandbox``.

The HA Core test suite owns the integration-level coverage (subprocess
spawn, restart budget, multi-group). These tests pin the runtime's
public contract: argparser, the constant the manager scans for, and that
``run()`` exits cleanly when shutdown is requested.
"""

import asyncio

from hass_client._proto import sandbox_pb2 as pb
from hass_client.channel import Channel, ChannelRemoteError
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.messages import MSG_CORE_CONFIG, MSG_READY
from hass_client.sandbox import SandboxRuntime
from hass_client.sandbox.__main__ import _build_parser
import pytest

from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import Event, callback
from homeassistant.util import dt as dt_util


async def _noop_channel_factory() -> Channel | None:
    """Channel factory that opens no channel — for in-process shutdown tests."""
    return None


class _LoopbackWriter:
    def __init__(self, target: asyncio.StreamReader) -> None:
        self._target = target

    def write(self, data: bytes) -> None:
        self._target.feed_data(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._target.feed_eof()

    async def wait_closed(self) -> None:
        return None


def _make_channel_pair() -> tuple[Channel, Channel]:
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    return (
        Channel(
            reader_a, _LoopbackWriter(reader_b), name="main", codec=ProtobufCodec()
        ),  # type: ignore[arg-type]
        Channel(
            reader_b, _LoopbackWriter(reader_a), name="sandbox", codec=ProtobufCodec()
        ),  # type: ignore[arg-type]
    )


def test_ready_msg_type_is_stable() -> None:
    """The Ready frame type is part of the manager↔runtime protocol."""
    assert MSG_READY == "sandbox/ready"


def test_cli_parser_accepts_name_and_url() -> None:
    """The CLI parser accepts the manager's argv and defaults log-level.

    The sandbox is not an authenticated principal inside main, so there is no
    ``--token`` argument any more (the runtime never used the credential).
    """
    parser = _build_parser()
    args = parser.parse_args(["--name", "built-in", "--url", "ws://x"])
    assert args.name == "built-in"
    assert args.url == "ws://x"
    assert args.log_level == "INFO"

    with pytest.raises(SystemExit):
        parser.parse_args([])

    # ``--token`` is gone: passing it is now an error.
    with pytest.raises(SystemExit):
        parser.parse_args(["--name", "built-in", "--token", "t"])


async def test_handlers_registered_before_ready(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Inbound call handlers are live the instant the Ready frame arrives.

    The manager only sends ``entry_setup`` once it sees Ready; if Ready
    raced ahead of handler registration, an immediate call would come back
    as ``ChannelUnknownType``. The probe issues a ``sandbox/ping`` call the
    moment Ready lands and asserts it resolves (handler present), not errors.
    """
    main_channel, sandbox_channel = _make_channel_pair()
    ready_seen = asyncio.Event()
    probe_result: list[object] = []

    async def _on_ready(_payload: object) -> None:
        try:
            probe_result.append(await main_channel.call("sandbox/ping", pb.Ping()))
        except ChannelRemoteError as err:
            probe_result.append(err)
        ready_seen.set()

    main_channel.register(MSG_READY, _on_ready)
    main_channel.start()

    async def _channel_factory() -> Channel:
        return sandbox_channel

    runtime = SandboxRuntime(
        url="ws://x",
        group="custom",
        channel_factory=_channel_factory,
    )

    task = asyncio.create_task(runtime.run())
    try:
        await asyncio.wait_for(ready_seen.wait(), timeout=5.0)
        assert len(probe_result) == 1
        # The ping handler answered: no ChannelUnknownType, a real PingResult.
        assert isinstance(probe_result[0], pb.PingResult)
        assert probe_result[0].pong == "sandbox"
    finally:
        runtime.request_shutdown()
        await asyncio.wait_for(task, timeout=5.0)
        await main_channel.close()
        await sandbox_channel.close()
    capsys.readouterr()


async def test_core_config_push_updates_private_hass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A live ``sandbox/core_config`` push lands on the private hass.

    The config values must be applied AND ``EVENT_CORE_CONFIG_UPDATE`` must
    fire on the private bus, so sandboxed integrations recompute exactly as
    they would locally.
    """
    main_channel, sandbox_channel = _make_channel_pair()
    ready_seen = asyncio.Event()

    async def _on_ready(_payload: object) -> None:
        ready_seen.set()

    main_channel.register(MSG_READY, _on_ready)
    main_channel.start()

    async def _channel_factory() -> Channel:
        return sandbox_channel

    runtime = SandboxRuntime(
        url="ws://x",
        group="custom",
        channel_factory=_channel_factory,
    )

    task = asyncio.create_task(runtime.run())
    original_tz = dt_util.get_default_time_zone()
    try:
        await asyncio.wait_for(ready_seen.wait(), timeout=5.0)
        flow_runner = runtime._flow_runner  # noqa: SLF001
        assert flow_runner is not None
        hass = flow_runner.hass

        events: list[Event] = []

        @callback
        def _on_core_config_update(event: Event) -> None:
            events.append(event)

        # Subscribe BEFORE pushing so the fired event cannot be missed.
        hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _on_core_config_update)

        await main_channel.push(
            MSG_CORE_CONFIG,
            pb.CoreConfig(
                latitude=52.3731,
                longitude=4.8926,
                time_zone="Europe/Amsterdam",
            ),
        )
        for _ in range(100):
            if events:
                break
            await asyncio.sleep(0.01)

        assert hass.config.latitude == 52.3731
        assert hass.config.longitude == 4.8926
        assert hass.config.time_zone == "Europe/Amsterdam"
        assert len(events) == 1
    finally:
        # The time-zone setter updates dt_util's process-global default —
        # restore it so the rest of the suite is unaffected.
        dt_util.set_default_time_zone(original_tz)
        runtime.request_shutdown()
        await asyncio.wait_for(task, timeout=5.0)
        await main_channel.close()
        await sandbox_channel.close()
    capsys.readouterr()


async def test_runtime_starts_in_locked_down_sharing_posture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The sandbox HA sees only its own entities — no subscription to main.

    There is no ``share_*`` config surface; the locked-down posture is
    a property of the runtime itself rather than a config flag. See
    ``sandbox/docs/design-share-states.md``
    for the future opt-in design.
    """
    runtime = SandboxRuntime(
        url="ws://x",
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
        group="built-in",
        # Pytest captures stdin/stdout; skip channel setup for this
        # in-process shutdown test (the real stdio path is covered
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
