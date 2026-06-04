"""Sandbox runtime — the long-running process inside one sandbox group.

Composes the sandbox's per-process services:

* :class:`FlowRunner` — drives integration ``ConfigFlow`` instances
  out-of-process.
* :class:`EntryRunner` — accepts ``sandbox/entry_setup`` pushes and
  runs ``async_setup_entry`` against the sandbox-private HA.
* :class:`EntityBridge` — pushes entity registrations + state changes
  back to main.
* :class:`ServiceMirror` / :class:`EventMirror` — mirror service
  registrations and ``<owned_domain>_*`` events up to main, gated by
  :class:`ApprovedDomains`.

The handshake: open the control channel (transport selected by the
``--url`` scheme — ``stdio://`` by default, ``unix://<path>`` to dial back
to the manager's unix socket), send a :data:`MSG_READY` frame as the first
message, warm-load restore state, register handlers, then idle until
SIGTERM (or until main asks for a graceful shutdown over the channel — see
:meth:`SandboxRuntime._handle_shutdown`).
"""

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import json
import logging
import os
import signal
import sys
import tempfile
from typing import Any

from hass_client._proto import sandbox_pb2 as pb
from hass_client.approved_domains import ApprovedDomains
from hass_client.channel import Channel
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.entity_bridge import EntityBridge
from hass_client.entry_runner import EntryRunner
from hass_client.event_mirror import EventMirror
from hass_client.flow_runner import FlowRunner
from hass_client.protocol import MSG_READY, MSG_SHUTDOWN
from hass_client.sandbox_bridge import ChannelSandboxBridge
from hass_client.service_mirror import ServiceMirror
from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import CoreState
from homeassistant.helpers import json as json_helper, restore_state
from homeassistant.helpers.sandbox_context import current_sandbox

_LOGGER = logging.getLogger(__name__)

ChannelFactory = Callable[[], Awaitable[Channel | None]]


class SandboxRuntime:
    """Runtime: Ready-frame handshake + length-prefixed control channel.

    The control-channel transport is chosen from the ``--url`` scheme:
    ``stdio://`` (default — frames over the process's stdin/stdout) or
    ``unix://<path>`` (dial back to the manager's unix socket). ``ws://`` /
    ``wss://`` are reserved for the deferred websocket transport and
    rejected for now. The handshake is a :data:`MSG_READY` frame sent as the
    channel's first message — there is no stdout text marker.
    """

    def __init__(
        self,
        *,
        url: str,
        group: str,
        config_dir: str | None = None,
        channel_factory: ChannelFactory | None = None,
    ) -> None:
        """Initialise the runtime with its main-HA connection parameters.

        ``channel_factory`` returns the live control channel — defaults to
        opening one over the process's stdin/stdout. Tests pass a factory
        that returns ``None`` (no channel) or an in-memory pair.
        """
        self.url = url
        self.group = group
        self._config_dir = config_dir
        self._channel_factory = channel_factory or self._default_channel_factory
        self._shutdown: asyncio.Event | None = None
        self._ready: asyncio.Event | None = None
        self._channel: Channel | None = None
        self._flow_runner: FlowRunner | None = None
        self._entry_runner: EntryRunner | None = None
        self._entity_bridge: EntityBridge | None = None
        self._service_mirror: ServiceMirror | None = None
        self._event_mirror: EventMirror | None = None
        self._approved = ApprovedDomains()

    @property
    def started(self) -> bool:
        """Whether ``run()`` has initialised its shutdown event."""
        return self._shutdown is not None

    async def wait_until_ready(self, *, timeout: float = 5.0) -> None:
        """Block until all channel handlers have been registered.

        ``started`` flips to True very early in :meth:`run` (right after
        the SIGTERM hook); tests that want to issue a channel call need
        to wait until the runtime has finished registering every
        handler. This event is set right before ``run`` awaits the
        shutdown signal.
        """
        if self._ready is None:
            raise RuntimeError("SandboxRuntime.run() has not been entered yet")
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    @property
    def channel(self) -> Channel | None:
        """The runtime's control channel, once ``run()`` has started it."""
        return self._channel

    def request_shutdown(self) -> None:
        """Request a graceful shutdown of the runtime."""
        if self._shutdown is None:
            raise RuntimeError("SandboxRuntime.run() has not been entered yet")
        self._shutdown.set()

    async def run(self) -> int:
        """Run until SIGTERM/SIGINT/shutdown-call arrives. Returns exit code."""
        loop = asyncio.get_running_loop()
        self._shutdown = asyncio.Event()
        self._ready = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._shutdown.set)

        _LOGGER.info("sandbox runtime ready (group=%s url=%s)", self.group, self.url)

        # Set up the HA instance + flow runner before the marker so the
        # first manager call after the handshake cannot race.
        cleanup_tempdir: tempfile.TemporaryDirectory[str] | None = None
        config_dir = self._config_dir
        if config_dir is None:
            cleanup_tempdir = tempfile.TemporaryDirectory(
                prefix=f"sandbox_{self.group}_"
            )
            config_dir = cleanup_tempdir.name

        self._flow_runner = await FlowRunner.create(config_dir=config_dir)
        hass = self._flow_runner.hass
        self._entry_runner = EntryRunner(hass, self._approved)
        self._entity_bridge = EntityBridge(hass, self._approved)
        self._service_mirror = ServiceMirror(hass, self._approved)
        self._event_mirror = EventMirror(hass, self._approved)

        self._channel = await self._channel_factory()
        sandbox_token: Any = None
        if self._channel is not None:
            # Route every `Store` IO to main via `current_sandbox`. The
            # contextvar is read at call time by `Store.async_load/save/
            # remove`, so it reaches Stores no matter how they imported the
            # class — including the helpers that captured the original
            # `Store` at module load (restore_state, the registries). It is
            # set BEFORE the warm-load and before any handler registers, so
            # every coroutine the runtime spawns inherits it (asyncio copies
            # the context at `create_task` time).
            #
            # Ordering caveat (see the plan's touch-points audit): registries
            # whose `Store` is constructed AND first loaded inside
            # `FlowRunner.create` already ran their `async_load` against the
            # sandbox tempdir before this point, so they keep their local
            # file backing. `restore_state`'s `async_load` runs *after* this
            # set, so it routes to main — which is what we want. If a future
            # refactor moves a registry's first `async_load` to straddle this
            # line, that registry would silently start routing to main.
            assert current_sandbox.get() is None, (
                "current_sandbox already set — two sandbox runtimes sharing "
                "one event loop? (see plan Risk #3)"
            )
            sandbox_token = current_sandbox.set(ChannelSandboxBridge(self._channel))
            # Start the channel reader first so the warm-load
            # round-trip can resolve, then pre-load this sandbox group's
            # restore-state cache. The contextvar (set above) routes the
            # load to main. The data lives on main under
            # ``.storage/sandbox/<group>/core.restore_state`` and was
            # written by the previous run's shutdown handler. Bare HA —
            # no bootstrap — so we call it ourselves; any RestoreEntity
            # that registers during entry_setup will see its prior state
            # cached. Handlers register *after* the warm-load so no
            # entry_setup can arrive before the cache is populated.
            self._channel.start()
            # Signal readiness as the channel's first outbound frame — the
            # manager flips to "running" on its arrival. Sent before the
            # warm-load so the handshake timing matches the old stdout
            # marker (which was written before warm-load too).
            await self._channel.push(MSG_READY)
            await _load_restore_state(hass)
            self._channel.register("sandbox/ping", _handle_ping)
            self._channel.register(MSG_SHUTDOWN, self._handle_shutdown)
            self._flow_runner.register(self._channel)
            self._entry_runner.register(self._channel)
            self._entity_bridge.register(self._channel)
            self._service_mirror.register(self._channel)
            self._event_mirror.register(self._channel)

        self._ready.set()
        try:
            await self._shutdown.wait()
        finally:
            _LOGGER.info("sandbox runtime shutting down (group=%s)", self.group)
            if self._event_mirror is not None:
                await self._event_mirror.async_stop()
            if self._service_mirror is not None:
                await self._service_mirror.async_stop()
            if self._entity_bridge is not None:
                await self._entity_bridge.async_stop()
            if self._channel is not None:
                await self._channel.close()
            if sandbox_token is not None:
                # Tidy test isolation; in prod the process exits anyway.
                current_sandbox.reset(sandbox_token)
            await self._flow_runner.async_stop()
            if cleanup_tempdir is not None:
                cleanup_tempdir.cleanup()
        return 0

    async def _default_channel_factory(self) -> Channel:
        """Open the control channel selected by the runtime's ``--url`` scheme.

        * ``stdio://`` (or empty) — frames ride the process's stdin/stdout.
        * ``unix://<path>`` — dial back to the manager's unix socket.
        * ``ws://`` / ``wss://`` — reserved for the deferred websocket
          transport; rejected here with a clear error (this build ships
          stdio + unix only).
        """
        kind = _transport_scheme(self.url)
        if kind == "unix":
            return await _open_unix_channel(
                self.url.removeprefix("unix://"), name=self.group
            )
        if kind == "ws":
            raise NotImplementedError(
                "websocket transport is not implemented in this build; it is "
                "reserved for the share-states work — use stdio:// or unix://"
            )
        return await _open_stdio_channel(name=self.group)

    async def _handle_shutdown(self, _payload: object) -> pb.ShutdownResult:
        """Unload entries, flush restore state, then exit cleanly.

        Runs inside the channel dispatcher so the reply is written before
        the runtime starts its teardown. The actual shutdown event is set
        via ``call_soon`` so the reply lands on the wire first; ``run()``
        then exits on the next loop turn through the existing finally
        block (which closes the channel, stops mirrors, etc.).
        """
        summary = await self._run_graceful_shutdown()
        if self._shutdown is not None:
            asyncio.get_running_loop().call_soon(self._shutdown.set)
        return summary

    async def _run_graceful_shutdown(self) -> pb.ShutdownResult:
        """Unload every loaded entry and snapshot RestoreEntity state.

        Fires ``EVENT_HOMEASSISTANT_FINAL_WRITE`` and waits for
        the bus to drain so ``Store``s with pending ``async_delay_save``
        writes flush to main via the ``current_sandbox`` bridge — the
        now-concurrent channel dispatcher means the re-entrant
        ``MSG_STORE_SAVE`` call each flush issues no longer deadlocks
        against this handler.

        Restore state is still **collected** (not flushed via the
        bridge) and returned in this reply: ``core.restore_state``
        is owned by the runtime's explicit warm-load / shutdown-dump path,
        not by an integration's ``Store``, so it doesn't ride the
        FINAL_WRITE flush. Shipping it back in the reply keeps the data
        path symmetric with the warm-load — main writes it via
        :meth:`SandboxBridge._handle_store_save`-style atomic write.
        """
        flow_runner = self._flow_runner
        if flow_runner is None:
            return pb.ShutdownResult(ok=True, unloaded=0)

        hass = flow_runner.hass
        unloaded = 0
        for entry in list(hass.config_entries.async_entries()):
            try:
                ok = await hass.config_entries.async_unload(entry.entry_id)
            except Exception:
                _LOGGER.exception(
                    "sandbox %s: async_unload(%s) raised",
                    self.group,
                    entry.entry_id,
                )
                continue
            if ok:
                unloaded += 1

        # Fire FINAL_WRITE so ``async_delay_save``-using
        # ``Store``s flush their pending data. Concurrent channel
        # dispatcher means each bridge write can re-enter the channel
        # without deadlocking against this handler.
        try:
            hass.set_state(CoreState.final_write)
            hass.bus.async_fire_internal(EVENT_HOMEASSISTANT_FINAL_WRITE)
            await hass.async_block_till_done()
        except Exception:
            _LOGGER.exception("sandbox %s: FINAL_WRITE flush failed", self.group)

        result = pb.ShutdownResult(ok=True, unloaded=unloaded)
        try:
            restore_data = restore_state.async_get(hass)
            stored = restore_data.async_get_stored_states()
            if stored:
                # Coerce HA-specific types (Fragment / State / datetime)
                # to plain primitives by round-tripping through orjson.
                # ``prepare_save_json`` is the same serialiser ``Store``
                # uses on its way to disk; we just intercept the bytes.
                wrapped = {
                    "version": restore_state.STORAGE_VERSION,
                    "minor_version": 1,
                    "key": restore_state.STORAGE_KEY,
                    "data": [item.as_dict() for item in stored],
                }
                _mode, json_bytes = json_helper.prepare_save_json(wrapped, encoder=None)
                result.restore_state.update(json.loads(json_bytes))
        except Exception:
            _LOGGER.exception("sandbox %s: restore-state collect failed", self.group)

        return result


async def _load_restore_state(hass: Any) -> None:
    """Warm-load this sandbox's ``core.restore_state`` cache.

    Calls :meth:`RestoreStateData.async_load` directly instead of
    :func:`restore_state.async_load`: the helper also wires up the
    periodic ``async_setup_dump`` listener via ``start.async_at_start``,
    which only fires on a fully-started HA. The sandbox's HA never goes
    through ``async_start``, so we skip that listener and rely on
    the shutdown handler to force the final dump.

    No store swap is needed: ``RestoreStateData`` builds a vanilla
    ``Store``, and ``Store.async_load`` reads ``current_sandbox`` at call
    time. Because the runtime set the contextvar before calling us, the
    load — and the later shutdown dump — round-trip through main no matter
    that ``restore_state.py`` captured the original ``Store`` reference at
    import time.
    """
    data = restore_state.async_get(hass)
    try:
        await data.async_load()
    except Exception:
        _LOGGER.exception("sandbox: failed to pre-load core.restore_state")


def _transport_scheme(url: str) -> str:
    """Map a ``--url`` to its transport kind.

    Returns ``"stdio"`` (empty / ``stdio://``), ``"unix"``
    (``unix://<path>``) or ``"ws"`` (``ws://`` / ``wss://``, reserved for
    the deferred websocket transport). Raises :class:`ValueError` for any
    other scheme.
    """
    if not url:
        return "stdio"
    scheme = url.split("://", 1)[0] if "://" in url else url
    if scheme in ("", "stdio"):
        return "stdio"
    if scheme == "unix":
        return "unix"
    if scheme in ("ws", "wss"):
        return "ws"
    raise ValueError(f"unsupported sandbox transport url: {url!r}")


async def _open_unix_channel(path: str, *, name: str) -> Channel:
    """Connect to the manager's unix socket and wrap it in a :class:`Channel`.

    The manager is the unix server; the runtime dials back here. Framing is
    the same length-prefixed :class:`~.channel.StreamTransport` the stdio
    path uses — a unix socket is just a different byte pipe under it, so no
    dedicated transport class is needed.
    """
    reader, writer = await asyncio.open_unix_connection(path)
    return Channel(reader, writer, name=name, codec=ProtobufCodec())


async def _open_stdio_channel(*, name: str) -> Channel:
    """Wrap the runtime's stdin/stdout into a :class:`Channel`."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(loop=loop)
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader, loop=loop),
        os.fdopen(sys.stdin.fileno(), "rb"),
    )
    transport, protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin,  # type: ignore[arg-type]
        os.fdopen(sys.stdout.fileno(), "wb"),
    )
    writer = asyncio.StreamWriter(transport, protocol, reader=None, loop=loop)
    return Channel(reader, writer, name=name, codec=ProtobufCodec())


async def _handle_ping(_payload: object) -> pb.PingResult:
    """Health-check handler — manager-side polling uses this round-trip."""
    return pb.PingResult(pong="sandbox")


__all__ = ["SandboxRuntime"]
