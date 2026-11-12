"""Sandbox runtime — the long-running process inside one sandbox group."""

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import logging
import os
import signal
import sys
import tempfile
from typing import Any

from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import json as json_helper, restore_state
from homeassistant.helpers.sandbox_context import current_sandbox
from homeassistant.helpers.translation import _async_get_component_strings
from homeassistant.loader import async_get_integrations
from homeassistant_sandbox._proto import sandbox_pb2 as pb
from homeassistant_sandbox.approved_domains import ApprovedDomains
from homeassistant_sandbox.channel import Channel
from homeassistant_sandbox.codec_protobuf import ProtobufCodec
from homeassistant_sandbox.entity_bridge import EntityBridge
from homeassistant_sandbox.entry_runner import EntryRunner, apply_core_config
from homeassistant_sandbox.entry_sync import EntrySync
from homeassistant_sandbox.event_mirror import EventMirror
from homeassistant_sandbox.flow_runner import FlowRunner
from homeassistant_sandbox.messages import (
    MSG_CORE_CONFIG,
    MSG_GET_TRANSLATIONS,
    MSG_PING,
    MSG_READY,
    MSG_SHUTDOWN,
    encode_json,
)
from homeassistant_sandbox.sandbox_bridge import ChannelSandboxBridge
from homeassistant_sandbox.service_mirror import ServiceMirror

_LOGGER = logging.getLogger(__name__)

ChannelFactory = Callable[[], Awaitable[Channel | None]]


class SandboxRuntime:
    """Runtime: Ready-frame handshake + length-prefixed control channel."""

    def __init__(
        self,
        *,
        url: str,
        group: str,
        config_dir: str | None = None,
        channel_factory: ChannelFactory | None = None,
    ) -> None:
        """Initialise the runtime with its main-HA connection parameters."""
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
        """Block until all channel handlers have been registered."""
        if self._ready is None:
            raise RuntimeError("SandboxRuntime.run() has not been entered yet")
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    @property
    def channel(self) -> Channel | None:
        """The runtime's control channel, once ``run()`` has started it."""
        return self._channel

    @property
    def hass(self) -> HomeAssistant | None:
        """The sandbox-private hass, once ``run()`` has created it."""
        return self._flow_runner.hass if self._flow_runner is not None else None

    @property
    def entity_bridge(self) -> EntityBridge | None:
        """The runtime's entity bridge, once ``run()`` has created it."""
        return self._entity_bridge

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
            # Set routing before creating handlers so their tasks inherit the storage context.
            assert current_sandbox.get() is None, (
                "current_sandbox already set — two sandbox runtimes sharing "
                "one event loop?"
            )
            sandbox_token = current_sandbox.set(ChannelSandboxBridge(self._channel))
            # Start the reader before restore-state loading, which calls back into main.
            self._channel.start()
            # Install handlers before readiness allows main to send entry setup calls.
            self._channel.register(MSG_PING, _handle_ping)
            self._channel.register(MSG_SHUTDOWN, self._handle_shutdown)
            self._channel.register(MSG_GET_TRANSLATIONS, self._handle_get_translations)
            self._channel.register(MSG_CORE_CONFIG, self._handle_core_config)
            entry_sync = EntrySync(hass, self._channel, lambda entry: True)
            self._entry_runner.entry_sync = entry_sync
            self._entity_bridge.entry_sync = entry_sync
            self._flow_runner.entry_sync = entry_sync
            self._flow_runner.register(self._channel)
            self._entry_runner.register(self._channel)
            self._entity_bridge.register(self._channel)
            self._service_mirror.register(self._channel)
            self._event_mirror.register(self._channel)
            # Load restore state before readiness so new entities see their previous values.
            await _load_restore_state(hass)
            # Ready is the LAST frame sent: handlers are up and the restore
            # cache is warm, so every entry_setup the manager now sends lands
            # on a registered, ready handler.
            await hass.async_start()
            await self._channel.push(MSG_READY)

        if self._channel is None:
            await hass.async_start()
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
                # Drain the shutdown reply before closing the channel cancels its handler.
                if self._entry_runner.entry_sync is not None:
                    await self._entry_runner.entry_sync.async_stop()
                await self._channel.drain_inflight()
                await self._channel.close()
            if sandbox_token is not None:
                # Tidy test isolation; in prod the process exits anyway.
                current_sandbox.reset(sandbox_token)
            await self._flow_runner.async_stop()
            if cleanup_tempdir is not None:
                cleanup_tempdir.cleanup()
        return 0

    async def _default_channel_factory(self) -> Channel:
        """Open the control channel selected by the runtime's ``--url`` scheme."""
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
        """Unload entries, flush restore state, then exit cleanly."""
        summary = await self._run_graceful_shutdown()
        if self._shutdown is not None:
            asyncio.get_running_loop().call_soon(self._shutdown.set)
        return summary

    async def _handle_get_translations(
        self, msg: pb.GetTranslations
    ) -> pb.GetTranslationsResult:
        """Serve a main-side ``sandbox/get_translations`` pull."""
        result = pb.GetTranslationsResult(language=msg.language)
        flow_runner = self._flow_runner
        if flow_runner is None:
            return result
        strings = await _collect_component_strings(
            flow_runner.hass, msg.language, list(msg.domains)
        )
        if strings:
            result.strings = encode_json(strings)
        return result

    async def _handle_core_config(self, msg: pb.CoreConfig) -> None:
        """Apply a live core-config update pushed from main."""
        flow_runner = self._flow_runner
        if flow_runner is None:
            return
        hass = flow_runner.hass
        await apply_core_config(hass, msg)
        hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE)

    async def _run_graceful_shutdown(self) -> pb.ShutdownResult:
        """Unload every loaded entry and snapshot RestoreEntity state."""
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

        # Flush delayed stores before shutdown acknowledges completion.
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
                # via ``prepare_save_json`` — the same serialiser ``Store``
                # uses on its way to disk — and ship the JSON bytes as-is.
                wrapped = {
                    "version": restore_state.STORAGE_VERSION,
                    "minor_version": 1,
                    "key": restore_state.STORAGE_KEY,
                    "data": [item.as_dict() for item in stored],
                }
                _mode, json_data = json_helper.prepare_save_json(wrapped, encoder=None)
                result.restore_state = (
                    json_data
                    if isinstance(json_data, bytes)
                    else json_data.encode("utf-8")
                )
        except Exception:
            _LOGGER.exception("sandbox %s: restore-state collect failed", self.group)

        return result


async def _collect_component_strings(
    hass: HomeAssistant, language: str, domains: list[str]
) -> dict[str, Any]:
    """Load raw translation strings for ``domains`` from this sandbox's disk."""
    if not domains:
        return {}
    components = set(domains)
    ints_or_excs = await async_get_integrations(hass, components)
    integrations = {
        domain: result
        for domain, result in ints_or_excs.items()
        if not isinstance(result, Exception)
    }
    by_language = await _async_get_component_strings(
        hass, [language], components, integrations
    )
    return by_language.get(language, {})


async def _load_restore_state(hass: Any) -> None:
    """Warm-load this sandbox's ``core.restore_state`` cache."""
    data = restore_state.async_get(hass)
    try:
        await data.async_load()
    except Exception:
        _LOGGER.exception("sandbox: failed to pre-load core.restore_state")


def _transport_scheme(url: str) -> str:
    """Map a ``--url`` to its transport kind."""
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
    """Connect to the manager's unix socket and wrap it in a :class:`Channel`."""
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
