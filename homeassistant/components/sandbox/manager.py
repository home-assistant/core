"""Sandbox — subprocess lifecycle and supervision.

Phase 3 building block. The manager owns one supervised subprocess per
sandbox group (``main`` / ``built-in`` / ``custom``); higher phases call
:meth:`SandboxManager.ensure_started` lazily as config entries are routed.

The contract between manager and runtime is:

* the manager launches ``python -m hass_client.sandbox`` and tells it
  which control-channel transport to use via ``--url``
* the runtime opens the control channel and sends a :data:`MSG_READY`
  frame as its first message once it is up (no stdout text marker)
* on ``SIGTERM`` the runtime exits cleanly

Two transports are supported (selected by :class:`SandboxManager`'s
``transport`` option, defaulting to ``stdio``):

* **stdio** — frames ride the subprocess's stdin/stdout pipes
  (``--url stdio://``); the default, unchanged from earlier phases.
* **unix** — the manager opens a unix-domain socket, passes its path as
  ``--url unix://<path>``, and the runtime dials back; the manager is the
  server. Both transports share :class:`~.channel.StreamTransport`'s
  length-prefixed framing, so there is no dedicated unix transport class.
"""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
import contextlib
from dataclasses import dataclass
import logging
import os
import shutil
import sys
import tempfile
import time
from typing import Any

from homeassistant.core import HomeAssistant

from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .codec_protobuf import ProtobufCodec
from .protocol import MSG_READY, MSG_SHUTDOWN

_LOGGER = logging.getLogger(__name__)

DEFAULT_RESTART_LIMIT = 3
DEFAULT_RESTART_WINDOW = 60.0
DEFAULT_RESTART_BACKOFF = 1.0
DEFAULT_READY_TIMEOUT = 30.0
DEFAULT_SHUTDOWN_GRACE = 10.0

# A command factory receives ``(group, url)`` — the manager decides the
# control-channel URL from its transport and hands it to the factory so the
# spawned argv carries the right ``--url``.
CommandFactory = Callable[[str, str], list[str]]
TokenFactory = Callable[[str], Awaitable[str]]

# Supported control-channel transports.
TRANSPORT_STDIO = "stdio"
TRANSPORT_UNIX = "unix"
_TRANSPORTS = (TRANSPORT_STDIO, TRANSPORT_UNIX)
# The reply is a protobuf ``ShutdownResult``; typed loosely to keep the
# manager free of a proto import.
ShutdownReplyCallback = Callable[[str, Any], Awaitable[None]]


class SandboxV2Error(Exception):
    """Base class for sandbox lifecycle errors."""


class SandboxStartError(SandboxV2Error):
    """Sandbox did not reach the ``running`` state."""


class SandboxFailedError(SandboxV2Error):
    """Sandbox crashed more than the configured restart limit allows."""


@dataclass(frozen=True)
class SandboxConfig:
    """Tunables for one supervised sandbox process."""

    restart_limit: int = DEFAULT_RESTART_LIMIT
    restart_window: float = DEFAULT_RESTART_WINDOW
    restart_backoff: float = DEFAULT_RESTART_BACKOFF
    ready_timeout: float = DEFAULT_READY_TIMEOUT
    shutdown_grace: float = DEFAULT_SHUTDOWN_GRACE


class SandboxProcess:
    """One supervised sandbox subprocess.

    States cycle through ``stopped`` → ``starting`` → ``running`` →
    (``starting`` on crash) → ``failed`` once the restart budget is spent.
    """

    def __init__(
        self,
        group: str,
        command_factory: Callable[[str], list[str]],
        config: SandboxConfig,
        *,
        transport: str = TRANSPORT_STDIO,
        on_failed: Callable[[str], None] | None = None,
        on_channel_ready: Callable[[str, Channel], None] | None = None,
        on_shutdown_reply: ShutdownReplyCallback | None = None,
    ) -> None:
        """Initialise a supervised sandbox subprocess.

        ``command_factory`` is called with the control-channel URL the
        chosen ``transport`` requires (``stdio://`` or ``unix://<path>``)
        and returns the argv to spawn.

        ``on_channel_ready`` is invoked with the live :class:`Channel` as
        soon as it is opened — before the runtime's :data:`MSG_READY`
        frame arrives — so its handlers are in place before the runtime's
        own warm-load round-trip lands. It runs synchronously on the
        manager's loop.

        ``on_shutdown_reply`` is invoked with the runtime's reply to
        :data:`MSG_SHUTDOWN` (Phase 9) so the caller can persist any
        ``restore_state`` payload before the subprocess exits.
        """
        self.group = group
        self._command_factory = command_factory
        self._config = config
        self._transport = transport
        self._on_failed = on_failed
        self._on_channel_ready = on_channel_ready
        self._on_shutdown_reply = on_shutdown_reply
        self._state: str = "stopped"
        self._process: asyncio.subprocess.Process | None = None
        self._supervisor: asyncio.Task[None] | None = None
        self._ready: asyncio.Event = asyncio.Event()
        self._stopped: asyncio.Event = asyncio.Event()
        self._stopped.set()
        self._stopping: bool = False
        self._attempts: deque[float] = deque()
        self._channel: Channel | None = None

    @property
    def state(self) -> str:
        """Current lifecycle state."""
        return self._state

    @property
    def pid(self) -> int | None:
        """PID of the live subprocess, or ``None`` if not running."""
        proc = self._process
        return proc.pid if proc is not None and proc.returncode is None else None

    @property
    def channel(self) -> Channel | None:
        """The active control channel, or None when not running."""
        return self._channel

    async def start(self) -> None:
        """Spawn the subprocess and block until it is ``running``.

        Raises :class:`SandboxStartError` if the supervisor gives up or the
        ready handshake times out.
        """
        if self._supervisor is not None:
            return
        self._stopping = False
        self._stopped.clear()
        self._ready.clear()
        self._state = "starting"
        self._attempts.clear()
        self._supervisor = asyncio.create_task(
            self._supervise(), name=f"sandbox[{self.group}]"
        )

        ready_task = asyncio.create_task(self._ready.wait())
        stopped_task = asyncio.create_task(self._stopped.wait())
        try:
            await asyncio.wait(
                {ready_task, stopped_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=self._config.ready_timeout,
            )
        finally:
            for task in (ready_task, stopped_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

        if self._state == "running":
            return

        await self.stop()
        raise SandboxStartError(
            f"Sandbox {self.group!r} failed to start (state={self._state})"
        )

    async def stop(self) -> None:
        """Terminate the subprocess and wait for the supervisor to exit."""
        self._stopping = True
        proc = self._process
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=self._config.shutdown_grace)
            except TimeoutError:
                _LOGGER.warning(
                    "Sandbox %s did not exit on SIGTERM within %.1fs; sending SIGKILL",
                    self.group,
                    self._config.shutdown_grace,
                )
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(BaseException):
                    await proc.wait()

        supervisor = self._supervisor
        if supervisor is not None:
            try:
                await supervisor
            finally:
                self._supervisor = None

        if self._state != "failed":
            self._state = "stopped"

    async def async_graceful_shutdown(self, *, timeout: float) -> bool:
        """Phase 9: ask the runtime to unload + flush, then wait for exit.

        Sends ``sandbox/shutdown`` over the live channel and waits up
        to ``timeout`` for the runtime to reply and then exit on its
        own. Sets :attr:`_stopping` first so the supervisor does not
        treat the clean exit as a crash. Returns ``True`` if the process
        exited within the grace, ``False`` if anything went wrong
        (timeout, no channel, channel closed) — in which case the
        caller should fall through to :meth:`stop` for SIGTERM/SIGKILL.

        ``on_reply`` is invoked with the dict the runtime returns (the
        ``restore_state`` payload + summary counters) so the caller can
        persist it before the channel goes away.
        """
        self._stopping = True
        channel = self._channel
        proc = self._process
        if channel is None or channel.closed or proc is None:
            return False
        if proc.returncode is not None:
            return True

        try:
            reply = await channel.call(MSG_SHUTDOWN, None, timeout=timeout)
        except TimeoutError:
            _LOGGER.warning(
                "Sandbox %s did not reply to shutdown within %.1fs",
                self.group,
                timeout,
            )
            return False
        except (ChannelClosedError, ChannelRemoteError) as err:
            _LOGGER.debug(
                "Sandbox %s shutdown call failed (%s); falling back to SIGTERM",
                self.group,
                err,
            )
            return False

        callback = self._on_shutdown_reply
        if callback is not None:
            try:
                await callback(self.group, reply)
            except Exception:
                _LOGGER.exception(
                    "Sandbox %s on_shutdown_reply callback raised", self.group
                )

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except TimeoutError:
            _LOGGER.warning(
                "Sandbox %s acked shutdown but did not exit within %.1fs",
                self.group,
                timeout,
            )
            return False
        return True

    async def _supervise(self) -> None:
        """Loop spawning the subprocess, applying the restart budget."""
        try:
            while not self._stopping:
                now = time.monotonic()
                while (
                    self._attempts
                    and now - self._attempts[0] > self._config.restart_window
                ):
                    self._attempts.popleft()
                if len(self._attempts) >= self._config.restart_limit:
                    _LOGGER.error(
                        "Sandbox %s exceeded restart limit (%d attempts in %.0fs);"
                        " marking failed",
                        self.group,
                        self._config.restart_limit,
                        self._config.restart_window,
                    )
                    self._state = "failed"
                    if self._on_failed is not None:
                        try:
                            self._on_failed(self.group)
                        except Exception:
                            _LOGGER.exception(
                                "Sandbox %s on_failed callback raised", self.group
                            )
                    return

                self._attempts.append(now)
                self._state = "starting"
                self._ready.clear()
                await self._run_one()

                if self._stopping:
                    return

                _LOGGER.warning(
                    "Sandbox %s exited unexpectedly; restarting in %.2fs",
                    self.group,
                    self._config.restart_backoff,
                )
                try:
                    await asyncio.sleep(self._config.restart_backoff)
                except asyncio.CancelledError:
                    return
        finally:
            if self._state != "failed":
                self._state = "stopped"
            self._stopped.set()

    async def _run_one(self) -> None:
        """Spawn one process attempt and wait for it to exit."""
        if self._transport == TRANSPORT_UNIX:
            await self._run_one_unix()
        else:
            await self._run_one_stdio()

    async def _run_one_stdio(self) -> None:
        """Spawn over stdio: the channel rides the subprocess's pipes."""
        proc = await self._spawn(self._command_factory("stdio://"))
        if proc is None:
            return
        self._process = proc
        try:
            # Open the channel up front — stdout carries nothing but frames
            # now. Handlers go on before the reader starts so the runtime's
            # warm-load round-trip (and any early push) is never dropped.
            assert proc.stdout is not None
            assert proc.stdin is not None
            self._channel = self._build_channel(proc.stdout, proc.stdin)
            await self._supervise_until_exit(proc, self._channel, drain_stdout=False)
        finally:
            self._process = None

    async def _run_one_unix(self) -> None:
        """Spawn over a unix socket: the manager listens, runtime dials back.

        The socket lives in a short-lived per-attempt tempdir rather than
        under the (possibly long) config dir, sidestepping the ~108-char
        ``sun_path`` limit on Linux. It is unlinked when the server closes
        and the tempdir is removed on the way out — no leaked socket file.
        """
        socket_dir = tempfile.mkdtemp(prefix=f"sandbox_{self.group}_")
        socket_path = os.path.join(socket_dir, "control.sock")
        loop = asyncio.get_running_loop()
        connected: asyncio.Future[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = (
            loop.create_future()
        )

        def _on_connect(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            if connected.done():
                # Only the first (runtime) connection is honoured.
                writer.close()
                return
            connected.set_result((reader, writer))

        server = await asyncio.start_unix_server(_on_connect, path=socket_path)
        try:
            proc = await self._spawn(self._command_factory(f"unix://{socket_path}"))
            if proc is None:
                return
            self._process = proc
            try:
                # The runtime connects back as part of its startup; race the
                # accept against an early exit so a crash-before-connect does
                # not hang here forever.
                exit_task = asyncio.create_task(proc.wait())
                waiters: set[asyncio.Future[Any]] = {connected, exit_task}
                try:
                    await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    if not exit_task.done():
                        exit_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await exit_task
                if not connected.done():
                    _LOGGER.warning(
                        "Sandbox %s exited before connecting to its control socket",
                        self.group,
                    )
                    return
                reader, writer = connected.result()
                self._channel = self._build_channel(reader, writer)
                await self._supervise_until_exit(proc, self._channel, drain_stdout=True)
            finally:
                self._process = None
        finally:
            server.close()
            # The accepted connection may linger in the server's client set:
            # when the runtime exits, the channel's read loop sees EOF and
            # marks the channel closed, so the later ``channel.close()`` is a
            # no-op that never closes the accepted transport. Force-close any
            # such leftover so ``wait_closed()`` cannot block forever.
            server.close_clients()
            with contextlib.suppress(Exception):
                await server.wait_closed()
            shutil.rmtree(socket_dir, ignore_errors=True)

    async def _spawn(self, command: list[str]) -> asyncio.subprocess.Process | None:
        """Spawn the subprocess, returning ``None`` if it cannot start."""
        try:
            return await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            _LOGGER.exception(
                "Sandbox %s could not be spawned (%s)", self.group, command
            )
            return None

    async def _supervise_until_exit(
        self,
        proc: asyncio.subprocess.Process,
        channel: Channel,
        *,
        drain_stdout: bool,
    ) -> None:
        """Wire the ready handshake, run until the process exits, clean up.

        Shared by both transports — they reach here with a live channel and
        a running process; only how the channel's byte pipe was obtained
        differs. ``drain_stdout`` is set for the unix transport, where the
        subprocess's stdout pipe is unused (frames ride the socket) and must
        still be drained so its buffer never fills.
        """
        ready_frame = asyncio.Event()

        async def _on_ready(_payload: object) -> None:
            ready_frame.set()

        channel.register(MSG_READY, _on_ready)
        if self._on_channel_ready is not None:
            try:
                self._on_channel_ready(self.group, channel)
            except Exception:
                _LOGGER.exception(
                    "Sandbox %s on_channel_ready callback raised", self.group
                )
        channel.start()

        ready_task = asyncio.create_task(ready_frame.wait())
        exit_task = asyncio.create_task(proc.wait())
        drain_tasks = [asyncio.create_task(self._drain_stream(proc.stderr, "stderr"))]
        if drain_stdout:
            drain_tasks.append(
                asyncio.create_task(self._drain_stream(proc.stdout, "stdout"))
            )

        try:
            await asyncio.wait(
                {ready_task, exit_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if ready_task.done() and not ready_task.cancelled():
                self._state = "running"
                self._ready.set()
                # Hold here until the process exits.
                await exit_task
        finally:
            for task in (ready_task, exit_task, *drain_tasks):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            if self._channel is not None:
                await self._channel.close()
                self._channel = None
            self._ready.clear()

    def _build_channel(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> Channel:
        """Wrap a reader/writer pair in a :class:`Channel`.

        Length-prefixed channel frames cross end-to-end — there is no text
        preamble. The pair comes from the subprocess's stdout/stdin (stdio)
        or from the accepted unix-socket connection (unix); the channel core
        is identical either way.
        """
        return Channel(reader, writer, name=self.group, codec=ProtobufCodec())

    async def _drain_stream(
        self, stream: asyncio.StreamReader | None, name: str
    ) -> None:
        """Read a child stream so its buffer never fills."""
        if stream is None:
            return
        while True:
            line = await stream.readline()
            if not line:
                return
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                _LOGGER.debug("sandbox %s %s: %s", self.group, name, text)


class SandboxManager:
    """Owns one :class:`SandboxProcess` per group, started lazily."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        command_factory: CommandFactory | None = None,
        config: SandboxConfig | None = None,
        on_failed: Callable[[str], None] | None = None,
        on_channel_ready: Callable[[str, Channel], None] | None = None,
        on_shutdown_reply: ShutdownReplyCallback | None = None,
        token_factory: TokenFactory | None = None,
        transport: str = TRANSPORT_STDIO,
    ) -> None:
        """Initialise the manager.

        ``command_factory`` lets tests substitute the spawned command; it is
        called with ``(group, url)`` and the default builds the
        ``python -m hass_client.sandbox`` argv that
        :class:`hass_client.sandbox.SandboxRuntime` consumes.

        ``transport`` selects the control-channel transport for every
        spawned sandbox: ``"stdio"`` (default — unchanged behavior) or
        ``"unix"`` (the manager opens a unix socket and the runtime dials
        back). Unix is opt-in so existing deployments keep using stdio.

        ``on_channel_ready`` is invoked once a sandbox's control channel is
        live; Phase 4's router uses it to register inbound flow handlers
        (e.g., ``sandbox/notify_flow_changed``).

        ``token_factory`` returns the scoped access token the manager
        passes to the subprocess (Phase 7). Awaited once per group and
        cached on :attr:`_tokens`. Without one, ``_default_command``
        falls back to a placeholder so tests that don't care about auth
        still work.
        """
        self._hass = hass
        self._command_factory = command_factory or self._default_command
        self._config = config or SandboxConfig()
        self._on_failed = on_failed
        self._on_channel_ready = on_channel_ready
        self._on_shutdown_reply = on_shutdown_reply
        self._token_factory = token_factory
        if transport not in _TRANSPORTS:
            raise ValueError(
                f"unknown sandbox transport {transport!r}; expected one of "
                f"{_TRANSPORTS}"
            )
        self._transport = transport
        self._tokens: dict[str, str] = {}
        self._sandboxes: dict[str, SandboxProcess] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def shutdown_grace(self) -> float:
        """Configured grace window for ``async_graceful_shutdown_all``."""
        return self._config.shutdown_grace

    @property
    def sandboxes(self) -> dict[str, SandboxProcess]:
        """Live read-only-ish view of the supervised processes."""
        return dict(self._sandboxes)

    def get(self, group: str) -> SandboxProcess | None:
        """Return the sandbox for ``group`` if one has ever been requested."""
        return self._sandboxes.get(group)

    async def ensure_started(self, group: str) -> SandboxProcess:
        """Return a running sandbox for ``group``, spawning it if needed.

        Raises :class:`SandboxFailedError` if the sandbox has already
        exhausted its restart budget and :class:`SandboxStartError` if a
        fresh spawn cannot reach ``running``.
        """
        lock = self._locks.setdefault(group, asyncio.Lock())
        async with lock:
            existing = self._sandboxes.get(group)
            if existing is not None:
                if existing.state in ("starting", "running"):
                    return existing
                if existing.state == "failed":
                    raise SandboxFailedError(f"Sandbox {group!r} is in a failed state")
                # Was stopped — drop the stale process and re-spawn.
                del self._sandboxes[group]

            if self._token_factory is not None and group not in self._tokens:
                self._tokens[group] = await self._token_factory(group)

            # Keeping the SandboxProcess in the map after a failed start lets
            # callers observe its state — ensure_started won't try to
            # restart a failed sandbox.
            def make_command(url: str) -> list[str]:
                return self._command_factory(group, url)

            process = SandboxProcess(
                group,
                make_command,
                self._config,
                transport=self._transport,
                on_failed=self._on_failed,
                on_channel_ready=self._on_channel_ready,
                on_shutdown_reply=self._on_shutdown_reply,
            )
            self._sandboxes[group] = process
            await process.start()
            return process

    async def async_stop(self, group: str) -> None:
        """Stop one sandbox if it exists."""
        process = self._sandboxes.get(group)
        if process is None:
            return
        await process.stop()

    async def async_stop_all(self) -> None:
        """Stop every supervised sandbox in parallel."""
        if not self._sandboxes:
            return
        await asyncio.gather(
            *(process.stop() for process in self._sandboxes.values()),
            return_exceptions=True,
        )

    async def async_graceful_shutdown_all(self, *, timeout: float) -> None:
        """Phase 9: ask every running sandbox to shut down gracefully.

        Best-effort fan-out. Sandboxes that did not ack inside ``timeout``
        are left for :meth:`async_stop_all` to clean up with SIGTERM /
        SIGKILL — this method never raises.
        """
        if not self._sandboxes:
            return
        await asyncio.gather(
            *(
                process.async_graceful_shutdown(timeout=timeout)
                for process in self._sandboxes.values()
                if process.state == "running"
            ),
            return_exceptions=True,
        )

    def _default_command(self, group: str, url: str) -> list[str]:
        """Argv for ``python -m hass_client.sandbox``.

        ``url`` is the control-channel URL the manager's transport requires
        (``stdio://`` or ``unix://<path>``) — the runtime reads its scheme
        to pick the transport. Phase 7's scoped sandbox access token is
        still passed for the deferred websocket transport, which is the only
        path that consumes it.
        """
        token = self._tokens.get(group, "sandbox_placeholder")
        return [
            sys.executable,
            "-m",
            "hass_client.sandbox",
            "--name",
            group,
            "--url",
            url,
            "--token",
            token,
        ]


__all__ = [
    "TRANSPORT_STDIO",
    "TRANSPORT_UNIX",
    "CommandFactory",
    "SandboxConfig",
    "SandboxFailedError",
    "SandboxManager",
    "SandboxProcess",
    "SandboxStartError",
    "SandboxV2Error",
    "ShutdownReplyCallback",
    "TokenFactory",
]
