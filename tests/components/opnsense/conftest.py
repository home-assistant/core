"""Test fixtures and helpers for the OPNsense integration.

This module provides pytest fixtures, fake clients, and monkeypatch helpers
used across the integration's test suite to avoid network IO, neutralize
background tasks, and simplify Home Assistant testing.
"""

import asyncio
from collections.abc import MutableMapping
import contextlib
import inspect
import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import aiopnsense as _pyopnsense_mod
import pytest

import homeassistant.components.opnsense as _init_mod
from homeassistant.components.opnsense.const import CONF_DEVICE_UNIQUE_ID
import homeassistant.core as ha_core
from homeassistant.core import HomeAssistant
from homeassistant.util.async_ import get_scheduled_timer_handles

from tests.common import MockConfigEntry

# expose the pyopnsense module under the plain name for tests that
# import the fixture and expect `pyopnsense` to be available.
pyopnsense = _pyopnsense_mod


# Provide a shared FakeClientSession for tests to avoid creating real aiohttp sessions
class FakeClientSession:
    """Minimal fake client session used by tests in lieu of aiohttp.ClientSession."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the fake client session (no-op)."""

    async def __aenter__(self):
        """Enter async context and return the session-like object."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context, close the session and propagate exceptions."""
        await self.close()
        return False

    async def close(self):
        """Close the fake session (no-op)."""
        return True


def _ensure_async_create_task_mock(real, side_effect):
    """Ensure ``real.async_create_task`` is a MagicMock with the given side_effect.

    Attempt three strategies in order (matching the original logic):
    1. Direct assignment: real.async_create_task = MagicMock(side_effect=...)
    2. Use object.__setattr__ to bypass attribute protections.
    3. If an existing callable exists, wrap it with MagicMock(side_effect=lambda coro: orig(coro)).
    """
    with contextlib.suppress(AttributeError, TypeError):
        real.async_create_task = MagicMock(side_effect=side_effect)
    if not hasattr(real, "async_create_task") or not isinstance(
        getattr(real, "async_create_task", None), MagicMock
    ):
        # Try object.__setattr__ in case of attribute protections.
        with contextlib.suppress(AttributeError, TypeError):
            object.__setattr__(
                real, "async_create_task", MagicMock(side_effect=side_effect)
            )
    if not hasattr(real, "async_create_task") or not isinstance(
        getattr(real, "async_create_task", None), MagicMock
    ):
        # As a last resort, wrap an existing callable if present.
        orig = getattr(real, "async_create_task", None)
        if callable(orig):
            with contextlib.suppress(AttributeError, TypeError):
                object.__setattr__(
                    real,
                    "async_create_task",
                    MagicMock(side_effect=orig),
                )


@pytest.fixture(autouse=True)
def _patch_async_create_clientsession(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the integration's async_create_clientsession does not create real sessions.

    This prevents tests from opening real network resources and leaking connectors.
    """
    monkeypatch.setattr(
        _init_mod,
        "async_create_clientsession",
        lambda *a, **k: FakeClientSession(),
        raising=False,
    )


@pytest.fixture
def coordinator_capture():
    """Provide a reusable capture for created coordinator instances.

    Returns a small namespace-like object with two attributes:
    - instances: a list that will be appended with each created coordinator.
    - factory: a callable to pass into monkeypatch that will create the
      FakeCoordinator, append it to instances, and return it.
    """

    class _C:
        instances: list = []

        def __init__(self) -> None:
            self.instances = []

        def factory(self, coord_cls=None):
            # Return a factory function bound to coord_cls that captures instances.
            def _f(**kwargs):
                inst = (coord_cls or MagicMock)(**kwargs)
                self.instances.append(inst)
                return inst

            return _f

    return _C()


@pytest.fixture
def fake_stream_response_factory():
    r"""Return a factory that constructs a fake streaming response.

    Usage:
        resp = fake_stream_response_factory([b'data: {...}\n\n', b'data: {...}\n\n'])
        session.get = lambda *a, **k: resp

    The returned object implements:
      - .status / .reason / .ok
      - async context manager __aenter__/__aexit__
      - .content.iter_chunked(n) async generator yielding provided chunks
    """

    def _make(
        chunks: list[bytes], status: int = 200, reason: str = "OK", ok: bool = True
    ):
        class _Resp:
            def __init__(self) -> None:
                self.status = status
                self.reason = reason
                self.ok = ok

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            @property
            def content(self):
                class C:
                    def __init__(self, chunks: list[bytes]) -> None:
                        self._chunks = chunks

                    async def iter_chunked(self, _n):
                        for c in self._chunks:
                            yield c

                return C(list(chunks))

        return _Resp()

    return _make


@pytest.fixture
async def make_client():
    """Return a factory that constructs an OPNsenseClient for tests.

    This mirrors the local helper used in some test modules but exposes it as a
    fixture so tests can request it via parameters for consistency.
    """

    clients: list[pyopnsense.OPNsenseClient] = []

    def _make(
        session: aiohttp.ClientSession | None = None,
        username: str = "u",
        password: str = "p",
        url: str = "http://localhost",
    ) -> pyopnsense.OPNsenseClient:
        # Tests should not pass a real aiohttp.ClientSession. If session is
        # omitted, substitute the test FakeClientSession to avoid passing None
        # into the production client which expects a session-like object.
        if session is None:
            session = cast("aiohttp.ClientSession", FakeClientSession())
        client = pyopnsense.OPNsenseClient(
            url=url, username=username, password=password, session=session
        )
        clients.append(client)
        return client

    try:
        yield _make
    finally:
        # Ensure all created clients are closed to avoid leaking background tasks.
        for c in clients:
            with contextlib.suppress(Exception):
                await c.async_close()


# Module logger for test diagnostics
logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def _patch_homeassistant_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrap HomeAssistant.stop to ignore 'Event loop is closed' runtime errors.

    Some tests or integrations can close the event loop unexpectedly. During
    test teardown the pytest-homeassistant-custom-component plugin attempts to
    stop HomeAssistant instances which may call into a closed loop; this
    wrapper silently swallows that specific RuntimeError to allow teardown to
    continue in a best-effort manner.
    """

    original_stop = getattr(ha_core.HomeAssistant, "stop", None)

    if original_stop is None:
        return

    def _safe_stop(self, *args, **kwargs):
        try:
            return original_stop(self, *args, **kwargs)
        except RuntimeError as err:
            if "Event loop is closed" in str(err):
                # Log for diagnostics then swallow this specific error during tests.
                logger.exception(
                    "HomeAssistant.stop suppressed during test teardown: Event loop is closed",
                    exc_info=err,
                )
                return None
            raise

    monkeypatch.setattr(ha_core.HomeAssistant, "stop", _safe_stop, raising=False)


@pytest.fixture(autouse=True)
def _patch_asyncio_create_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch asyncio.create_task to avoid creating background workers for pyopnsense during tests.

    For coroutines created by pyopnsense, close the coroutine object and return a dummy task-like
    object to prevent "coroutine was never awaited" warnings while avoiding scheduling real
    background work during tests.
    """

    # keep a reference to the original so we can delegate for non-target coroutines
    # Prefer the one from the pyopnsense module if present, otherwise fall back
    # to the global asyncio.create_task.
    # Prefer the pyopnsense module's asyncio.create_task when available; fall
    # back to the global asyncio.create_task otherwise. Avoid relying on an
    # ImportError here since the module import already occurred at module
    # load time. Instead, detect presence safely using globals() and
    # getattr.
    if (
        "_pyopnsense_mod" in globals()
        and getattr(_pyopnsense_mod, "asyncio", None) is not None
    ):
        # Prefer the module-scoped asyncio.create_task when available so we can
        # delegate for non-target coroutines. Fall back to the global
        # asyncio.create_task if the module doesn't expose one.
        _original_create_task = getattr(
            _pyopnsense_mod.asyncio, "create_task", asyncio.create_task
        )
    else:
        # pyopnsense.asyncio is not present; delegate to the global
        # asyncio.create_task. We intentionally avoid patching the global
        # asyncio module below unless necessary.
        _original_create_task = asyncio.create_task
        logger.debug(
            "pyopnsense.asyncio not present; attaching minimal namespace with fake create_task; delegating others to global asyncio"
        )

    def _fake_create_task(coro, *args, **kwargs):
        # If the coroutine originates from pyopnsense background workers, close
        # it to avoid 'coroutine was never awaited' warnings and return a dummy
        # task-like object. Otherwise delegate to the original create_task.
        frame = getattr(coro, "cr_frame", None)
        module_name = ""
        if frame:
            try:
                g = getattr(frame, "f_globals", None) or {}
                module_name = (
                    g.get("__name__", "") if isinstance(g, MutableMapping) else ""
                )
            except AttributeError, TypeError:
                module_name = ""

        # Match module names that include 'pyopnsense' (e.g. 'homeassistant.components.opnsense.pyopnsense')
        if isinstance(module_name, str) and "pyopnsense" in module_name:
            with contextlib.suppress(Exception):
                coro.close()
            # Return an already-completed future if a running loop is present.
            try:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                fut.set_result(None)
            except RuntimeError:
                # No running loop; provide a minimally awaitable stub.
                class _DoneTask:
                    def done(self):
                        return True

                    def cancel(self):
                        return None

                    def cancelled(self):
                        return False

                    def result(self):
                        return None

                    def exception(self):
                        return None

                    def add_done_callback(self, cb):
                        with contextlib.suppress(Exception):
                            cb(self)

                    def __await__(self):
                        yield from ()

                return _DoneTask()
            else:
                return fut
        # Delegate to the original create_task for all other coroutines.
        return _original_create_task(coro, *args, **kwargs)

    # Patch create_task only on the pyopnsense module to avoid interfering
    # with the rest of the test environment (Home Assistant / pytest-asyncio).
    # If the pyopnsense module does not expose an `asyncio` attribute, attach
    # a minimal namespace with our patched create_task so tests that construct
    # OPNsenseClient outside a running loop do not attempt to schedule real
    # background work. This avoids touching the global asyncio module.
    try:
        # Construct a proxy object that delegates all attributes to the real
        # asyncio module except `create_task`, which we override with our
        # test-local `_fake_create_task`. This avoids mutating the global
        # asyncio module and confines behavior to the pyopnsense module.
        real_asyncio = getattr(_pyopnsense_mod, "asyncio", asyncio)

        class _AsyncioProxy:
            """Proxy delegating attribute access to the real asyncio module.

            Only `create_task` is implemented on the proxy to forward to the
            provided fake implementation; all other attributes are looked up
            on the underlying real asyncio module via __getattr__.
            """

            def __init__(self, real: Any, create_task_impl: Any) -> None:
                self._real = real
                # store the impl as a bound attribute so monkeypatch can
                # replace it later if needed
                self.create_task = create_task_impl

            def __getattr__(self, name):
                return getattr(self._real, name)

        proxy = _AsyncioProxy(real_asyncio, _fake_create_task)

        # Replace whatever the pyopnsense module exposes with our proxy so
        # calls like `pyopnsense.asyncio.create_task(...)` hit the proxy and
        # use the fake implementation while all other asyncio behavior
        # delegates to the real module.
        monkeypatch.setattr(_pyopnsense_mod, "asyncio", proxy, raising=False)
    except Exception:  # noqa: BLE001
        logger.debug(
            "Failed to attach asyncio proxy on pyopnsense; falling back to direct patching"
        )


@pytest.fixture(autouse=True)
def _neutralize_pyopnsense_background_tasks(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Autouse fixture to replace pyopnsense background queue workers with no-ops.

    This prevents the integration from scheduling background coroutines during
    tests which could interact with the event loop, create network IO, or
    produce 'coroutine was never awaited' warnings.
    """

    async def _noop_async(self, *args, **kwargs):
        return None

    # Try patching via the module/class object when available; fall back to
    # import-path based monkeypatching for resilience in different test envs.
    # Do not neutralize when running tests that exercise pyopnsense internals
    # directly (they need the real implementations). Skip patching for those
    # test modules (legacy tests/test_pyopnsense.py and split tests/pyopnsense/*).
    try:
        test_path = getattr(request, "fspath", None)
        if test_path:
            normalized_path = Path(str(test_path).replace("\\", "/"))
            path_parts = tuple(part.lower() for part in normalized_path.parts)
            has_pyopnsense_test_segments = any(
                path_parts[index : index + 2] == ("tests", "pyopnsense")
                for index in range(len(path_parts) - 1)
            )
            if (
                normalized_path.name == "test_pyopnsense.py"
                or has_pyopnsense_test_segments
            ):
                return
    except AttributeError, TypeError:
        # If we cannot determine the requesting test, continue with patching.
        pass

    try:
        if getattr(pyopnsense, "OPNsenseClient", None) is not None:
            monkeypatch.setattr(
                pyopnsense.OPNsenseClient, "_monitor_queue", _noop_async, raising=False
            )
            monkeypatch.setattr(
                pyopnsense.OPNsenseClient, "_process_queue", _noop_async, raising=False
            )
    except AttributeError, TypeError:
        # best-effort; continue to fallback below
        pass

    # Fallback to import path strings in case direct attribute access failed.
    with contextlib.suppress(Exception):
        monkeypatch.setattr(
            "aiopnsense.OPNsenseClient._monitor_queue",
            _noop_async,
            raising=False,
        )
    with contextlib.suppress(Exception):
        monkeypatch.setattr(
            "aiopnsense.OPNsenseClient._process_queue",
            _noop_async,
            raising=False,
        )

    # Also make our patched asyncio.create_task (defined earlier in this file)
    # recognize coroutines that are bound methods of OPNsenseClient even when
    # the coroutine object originates from the test module (for example when
    # tests replace the methods with test-local no-ops). Inspect the
    # coroutine frame locals and treat coroutines with a `self` that is an
    # OPNsenseClient as pyopnsense background workers.
    try:
        # If the module-level fake_create_task exists, decorate it to be more
        # permissive. We patch the pyopnsense.asyncio.create_task if present.
        target_asyncio = getattr(_pyopnsense_mod, "asyncio", None)
        if target_asyncio is not None and hasattr(target_asyncio, "create_task"):
            orig = target_asyncio.create_task

            def _wrap_create_task(coro, *args, **kwargs):
                frame = getattr(coro, "cr_frame", None)
                module_name = ""
                if frame:
                    try:
                        g = getattr(frame, "f_globals", None) or {}
                        module_name = (
                            g.get("__name__", "")
                            if isinstance(g, MutableMapping)
                            else ""
                        )
                    except AttributeError, TypeError:
                        module_name = ""

                # If the coroutine originates from a test-local no-op but is a
                # bound method (has 'self' local that's an OPNsenseClient),
                # treat it like a pyopnsense background worker.
                is_pyopnsense_bound = False
                if frame:
                    try:
                        locs = getattr(frame, "f_locals", {}) or {}
                        self_obj = locs.get("self")
                        if (
                            self_obj is not None
                            and getattr(pyopnsense, "OPNsenseClient", None) is not None
                            and isinstance(self_obj, pyopnsense.OPNsenseClient)
                        ):
                            is_pyopnsense_bound = True
                    except AttributeError, TypeError:
                        is_pyopnsense_bound = False

                if is_pyopnsense_bound or (
                    isinstance(module_name, str) and "pyopnsense" in module_name
                ):
                    with contextlib.suppress(AttributeError, TypeError):
                        coro.close()
                    try:
                        loop = asyncio.get_running_loop()
                        fut = loop.create_future()
                        fut.set_result(None)
                    except RuntimeError:

                        class _DoneTask:
                            def done(self):
                                return True

                            def cancel(self):
                                return None

                            def cancelled(self):
                                return False

                            def result(self):
                                return None

                            def exception(self):
                                return None

                            def add_done_callback(self, cb):
                                with contextlib.suppress(AttributeError, TypeError):
                                    cb(self)

                            def __await__(self):
                                yield from ()

                        return _DoneTask()
                    else:
                        return fut

                return orig(coro, *args, **kwargs)

            monkeypatch.setattr(
                target_asyncio, "create_task", _wrap_create_task, raising=False
            )
    except AttributeError, TypeError:
        # Best-effort; do not fail tests if this decoration cannot be applied.
        pass


@pytest.fixture
def coordinator():
    """Provide a lightweight coordinator mock for tests.

    Use MagicMock so that registering listeners (which happens synchronously) does not
    produce AsyncMock "never awaited" warnings. Tests that need async behavior can
    set specific async methods on the mock to AsyncMock.
    """
    return MagicMock()


class DummyCoordinator(MagicMock):
    """Lightweight coordinator mock used by the tests.

    Use a MagicMock so that callbacks registered synchronously do not create
    AsyncMock coroutines that are never awaited. Tests can set async
    attributes individually to AsyncMock when they need awaitable behavior.
    """


@pytest.fixture
def dummy_coordinator():
    """Provide a fresh DummyCoordinator instance for a test.

    Tests can request this fixture when they need a lightweight coordinator
    mock that behaves like the previous `DummyCoordinator()` constructor.
    """
    return DummyCoordinator()


@pytest.fixture
def fake_client():
    """Return a factory that constructs lightweight FakeClient instances for tests.

    Usage:
        client = fake_client()
        client = fake_client(device_id="other", firmware_version="1.0")
    """

    def _make(
        device_id: object = "dev1",
        firmware_version: str = "99.0",
        telemetry: dict | None = None,
        close_result: bool = True,
    ):
        class FakeClient:
            def __init__(self, **kwargs: Any) -> None:
                # allow explicit overrides via kwargs when tests call the production
                # client factory with parameters; prefer explicit args passed to
                # the fixture factory above.
                self._device_id = device_id
                self._firmware = firmware_version
                self._telemetry = telemetry or {}
                self._close_result = close_result

                # state for query counts used by coordinator tests
                self._query_counts_reset = False
                self._query_counts = 1

            async def get_device_unique_id(self, expected_id: str | None = None):
                return self._device_id

            async def get_host_firmware_version(self):
                return self._firmware

            async def async_close(self):
                return self._close_result

            async def get_telemetry(self):
                return self._telemetry

            async def reset_query_counts(self):
                # mark reset and return None (used by coordinator)
                self._query_counts_reset = True

            async def get_query_counts(self):
                return self._query_counts

            async def get_interfaces(self):
                return {"eth0": {"inbytes": 200, "outbytes": 100}}

            async def get_vnstat(self):
                return {"interface_count": 0, "interfaces": {}}

            async def get_openvpn(self):
                return {"servers": {}}

            async def get_wireguard(self):
                return {"servers": {}}

        return FakeClient

    return _make


@pytest.fixture
def fake_reg_factory():
    """Return a factory that constructs a configurable fake device registry.

    Usage:
        # registry where device does not exist
        fake = fake_reg_factory(device_exists=False)

        # registry where device exists and has id
        fake = fake_reg_factory(device_exists=True, device_id="removed-device-id")

    The returned object exposes:
      - async_get_device(self, *args, **kwargs) -> object | None
      - async_remove_device(self, *args, **kwargs) -> any
      - removed: boolean flag set to True when async_remove_device is called
    """

    def _make(
        device_exists: bool = False,
        device_id: str = "dev",
        remove_result: object | None = None,
    ):
        class _FakeReg:
            def __init__(self) -> None:
                self.removed = False
                self._device_exists = device_exists
                self._device_id = device_id
                self._remove_result = remove_result

            def async_get_device(self, *args, **kwargs):
                if self._device_exists:

                    class _D:
                        id = self._device_id

                    return _D()
                return None

            def async_remove_device(self, *args, **kwargs):
                # mirror previous tests which sometimes inspect a `removed` flag
                self.removed = True
                return self._remove_result

        return _FakeReg()

    return _make


@pytest.fixture
def fake_flow_client():
    """Return a factory that constructs a lightweight FakeClient used in flow tests.

    The returned factory when called yields a FakeClient class suitable for
    config/option flow validation paths and records calls to is_plugin_installed.
    """

    def _make(
        device_id: str = "unique-id",
        firmware: str = "25.1",
        plugin_installed: bool = False,
    ):
        class FakeFlowClient:
            """Configurable fake client for flow tests.

            Attributes:
                last_instance: class var pointing to last created instance

            """

            last_instance: FakeFlowClient | None = None

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                FakeFlowClient.last_instance = self
                self._is_plugin_called = 0
                self._device_id = device_id
                self._firmware = firmware
                self._plugin_installed = plugin_installed

            async def get_host_firmware_version(self) -> str:
                return self._firmware

            async def get_system_info(self) -> dict:
                return {"name": "OPNsense"}

            async def get_device_unique_id(self, expected_id: str | None = None) -> str:
                return self._device_id

            async def is_plugin_installed(self) -> bool:
                self._is_plugin_called += 1
                return self._plugin_installed

        return FakeFlowClient

    return _make


@pytest.fixture
def fake_coordinator():
    """Return a simple FakeCoordinator class tests can pass to coordinator_capture.factory.

    The class records when its refresh/shutdown methods are called and accepts
    kwargs such as `device_tracker_coordinator` to mirror prior test-local
    coordinator implementations.
    """

    class FakeCoordinator:
        def __init__(self, **kwargs: Any) -> None:
            # mirror existing tests which inspect this flag
            self._is_device_tracker = kwargs.get("device_tracker_coordinator", False)
            self.refreshed = False
            self.shut = False

        async def async_config_entry_first_refresh(self):
            # mark that initial refresh happened for assertions
            self.refreshed = True
            return True

        async def async_shutdown(self):
            # record that shutdown was invoked
            self.shut = True
            return True

    return FakeCoordinator


@pytest.fixture
def make_config_entry():
    """Return a factory for creating MockConfigEntry instances for tests.

    Usage:
        entry = make_config_entry()
        entry2 = make_config_entry(data={...}, title="MyTitle", unique_id="id", entry_id="eid", version=2, options={})

    Keyword args supported:
      - data: dict for entry.data (defaults to {CONF_DEVICE_UNIQUE_ID: 'test-device-123'})
      - title: entry title
      - unique_id: entry.unique_id
      - entry_id: entry.entry_id
      - version: entry.version
      - options: entry.options
      - runtime_data: value to assign to entry.runtime_data (default: MagicMock())
    """

    def _make(
        data: dict | None = None,
        *,
        title: str | None = None,
        unique_id: str | None = None,
        entry_id: str | None = None,
        version: int | None = None,
        options: dict | None = None,
        runtime_data: Any | None = None,
    ) -> MockConfigEntry:
        data = data or {CONF_DEVICE_UNIQUE_ID: "test-device-123"}
        entry = MockConfigEntry(
            domain="opnsense",
            data=data,
            title=(title if title is not None else "OPNSense Test"),
        )

        # Apply optional attributes using object.__setattr__ to bypass property protections.
        if unique_id is not None:
            object.__setattr__(entry, "unique_id", unique_id)
        if entry_id is not None:
            object.__setattr__(entry, "entry_id", entry_id)
        if version is not None:
            object.__setattr__(entry, "version", version)
        if options is not None:
            object.__setattr__(entry, "options", options)
        # runtime_data default is a MagicMock to support attribute-style access in tests
        entry.runtime_data = runtime_data if runtime_data is not None else MagicMock()
        return entry

    return _make


@pytest.fixture
def ph_hass(
    request: pytest.FixtureRequest,
    hass: HomeAssistant = cast(HomeAssistant, None),
) -> HomeAssistant | MagicMock:
    """Safe hass-like fixture: prefer real PHCC `hass` when available.

    Prefer the pytest-injected `hass` fixture when the pytest-homeassistant-
    custom-component plugin is present. To support environments where the
    plugin is absent (or where fixture injection order yields an async
    generator), fall back to using `request.getfixturevalue("hass")` only
    as a last resort; if that still isn't available, return a MagicMock
    that provides the minimal attributes tests expect.
    """

    # Helper used to schedule coroutines on the running loop when possible.
    def _schedule_or_return(coro):
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(coro)
        except RuntimeError:
            # No running loop available (unlikely in async tests); fall
            # back to returning the coroutine so callers can decide.
            return coro

    # helper _ensure_async_create_task_mock moved to module top-level

    # If pytest injected a `hass` fixture, prefer it (but avoid advancing
    # async-generator fixtures here). This lets pytest supply the real
    # PHCC hass instance when available without calling getfixturevalue.
    real = hass
    if real is not None:
        # If the injected fixture is an async-generator object, we must not
        # advance it here because its lifecycle is managed by the plugin
        # (treat as unavailable and fall back below).
        if inspect.isasyncgen(real):
            real = None
        else:
            # Reuse helper to ensure async_create_task is a MagicMock so tests
            # can assert `.called` etc.
            _ensure_async_create_task_mock(real, _schedule_or_return)
            return real

    # No injected hass or injected hass unusable; try the legacy fallback
    # of requesting the fixture by name. Only call getfixturevalue as a
    # safety net when injection did not occur.
    try:
        real = request.getfixturevalue("hass")
        if inspect.isasyncgen(real):
            real = None
        if real is not None:
            # Mirror the same robust assignment logic for the plugin-provided
            # hass fixture path using the helper.
            _ensure_async_create_task_mock(real, _schedule_or_return)
            return real
    except pytest.FixtureLookupError:
        # No PHCC hass available; will return MagicMock fallback below.
        pass

    # No real hass fixture available; return a MagicMock fallback.
    m = MagicMock()
    m.config_entries = MagicMock()
    m.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    m.config_entries.async_reload = AsyncMock(return_value=None)
    m.data = {}
    # Mirror HomeAssistant API used by the integration/tests.
    m.async_create_task = MagicMock(side_effect=_schedule_or_return)
    # provide a loop wrapper that cancels scheduled timer handles immediately
    # so the pytest-homeassistant-custom-component plugin does not report
    # lingering timers during test teardown.
    try:
        real_loop = asyncio.get_running_loop()
    except RuntimeError:
        real_loop = asyncio.new_event_loop()

    class FakeLoop:
        def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
            self._loop = loop

        def call_later(self, delay, callback, *args):
            handle = self._loop.call_later(delay, callback, *args)
            with contextlib.suppress(Exception):
                handle.cancel()
            return handle

        def __getattr__(self, name):
            return getattr(self._loop, name)

    m.loop = FakeLoop(real_loop)
    return m


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Tell the PHCC verify_cleanup fixture to allow lingering timers.

    Tests in this suite intentionally create short-lived timers; during the
    incremental migration we accept plugin warnings instead of hard failures.
    """
    return True


def pytest_runtest_teardown(item: Any, nextitem: Any) -> None:
    """Pytest hook: cancel any scheduled timer handles after each test.

    Prevent the pytest-homeassistant-custom-component plugin from failing tests
    due to lingering timer handles created by the integration (for example via
    hass.loop.call_later / async_call_later).
    """
    try:
        # Prefer the running loop when called from a running async context.
        event_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop; create a new event loop as a safe fallback.
        # This avoids using the deprecated `get_event_loop` path and mirrors
        # the recommended pattern for synchronous code needing a loop.
        event_loop = asyncio.new_event_loop()
    # If some integration code created and closed the global loop, we may
    # need to replace it with a fresh loop to allow the PHCC plugin to
    # perform teardown. However, this repository opts in to that behavior
    # via the `expected_lingering_timers` fixture. Only perform loop
    # replacement when the current test requested it; otherwise skip the
    # surgery but still attempt to cancel any scheduled timer handles in a
    # best-effort manner.
    if getattr(event_loop, "is_closed", lambda: False)():
        replace_loop = False
        try:
            # Prefer the fixture value for the current test if present.
            replace_loop = bool(item.funcargs.get("expected_lingering_timers", False))
        except AttributeError, KeyError:
            replace_loop = False

        if replace_loop:
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                event_loop = new_loop
            except OSError, RuntimeError:
                # Best-effort: if we cannot recreate the loop, continue and
                # let teardown attempt to proceed (it may still error).
                pass

    # Collect scheduled timer handles from the (possibly replaced) loop;
    # if the loop is closed and handle collection fails, skip cancellation
    # gracefully.
    try:
        handles = get_scheduled_timer_handles(event_loop)
    except RuntimeError, OSError:
        handles = []

    for handle in handles:
        # Best-effort cancellation; don't raise from teardown hook.
        with contextlib.suppress(Exception):
            if not handle.cancelled():
                handle.cancel()
