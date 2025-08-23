"""Common fixtures for the Grid connect tests."""

import asyncio
from collections.abc import Generator
from contextlib import ExitStack
import importlib
import sys
import types
from unittest.mock import AsyncMock, patch

import pytest

# Optional pytest-socket support
try:
    from pytest_socket import enable_socket, socket_allow_hosts
    HAS_PYTEST_SOCKET = True
except ImportError:  # pytest-socket not installed
    HAS_PYTEST_SOCKET = False

# Optional asyncio Windows internals import (must be top-level for lint compliance)
try:
    from asyncio import windows_events as _we  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    _we = None  # type: ignore[assignment]

# Optional Home Assistant runner import (top-level for lint compliance)
try:
    import homeassistant.runner as ha_runner  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001 - third-party optional import may fail for many reasons in test env
    ha_runner = None  # type: ignore[assignment]

# Ensure Windows uses the SelectorEventLoopPolicy to avoid Proactor issues in tests
if sys.platform == "win32":
    # Unconditionally set Selector policy at import time
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Guard against any later attempt to switch back to Proactor
    _orig_set_policy = asyncio.set_event_loop_policy

    def _guard_set_event_loop_policy(policy: asyncio.AbstractEventLoopPolicy) -> None:
        if isinstance(policy, getattr(asyncio, "WindowsProactorEventLoopPolicy", object)):
            policy = asyncio.WindowsSelectorEventLoopPolicy()
        _orig_set_policy(policy)

    asyncio.set_event_loop_policy = _guard_set_event_loop_policy  # type: ignore[assignment]

    # Alias Proactor constructs to Selector equivalents to prevent creation anywhere
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.WindowsProactorEventLoopPolicy = asyncio.WindowsSelectorEventLoopPolicy  # type: ignore[assignment]
    if hasattr(asyncio, "ProactorEventLoop"):
        asyncio.ProactorEventLoop = asyncio.SelectorEventLoop  # type: ignore[assignment]
    # Also patch the windows_events module classes used internally
    if _we is not None:
        _we.ProactorEventLoop = asyncio.SelectorEventLoop  # type: ignore[assignment]
        _we.WindowsProactorEventLoopPolicy = asyncio.WindowsSelectorEventLoopPolicy  # type: ignore[assignment]
    # Ensure default policy reference points to selector
    if hasattr(asyncio, "DefaultEventLoopPolicy"):
        asyncio.DefaultEventLoopPolicy = asyncio.WindowsSelectorEventLoopPolicy  # type: ignore[assignment]

@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Set selector loop policy and allow localhost sockets as early as possible.

    This runs before test collection, earlier than fixtures, to avoid pytest-asyncio
    creating a Proactor loop and to ensure pytest-socket allows asyncio internals.
    """
    if sys.platform == "win32":
        if isinstance(
            asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy
        ):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if HAS_PYTEST_SOCKET:
        enable_socket()
        socket_allow_hosts(["127.0.0.1", "::1", "localhost"])

    # Override Home Assistant's event loop factory early to force Selector on Windows
    if ha_runner is not None:
        def _new_event_loop_selector() -> asyncio.AbstractEventLoop:
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                loop = asyncio.SelectorEventLoop()
            else:
                policy = asyncio.get_event_loop_policy()
                loop = policy.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

        setattr(ha_runner, "new_event_loop", _new_event_loop_selector)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: pytest.Session) -> None:
    """Reinforce selector policy and socket allowances at session start."""
    if sys.platform == "win32":
        if isinstance(
            asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy
        ):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if HAS_PYTEST_SOCKET:
        enable_socket()
        socket_allow_hosts(["127.0.0.1", "::1", "localhost"])

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use WindowsSelectorEventLoopPolicy on Windows for compatibility."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session", autouse=True)
def force_selector_event_loop_for_homeassistant():
    """Deprecated: handled in pytest_configure for earlier application."""
    return

@pytest.fixture(scope="session")
def event_loop(event_loop_policy):
    """Provide a session-scoped event loop using Selector on Windows.

    This overrides pytest-asyncio's default session loop to avoid Proactor entirely.
    """
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = event_loop_policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def mock_zeroconf(monkeypatch):
    """Mock zeroconf to prevent real socket usage."""
    monkeypatch.setattr("zeroconf.Zeroconf", lambda *a, **kw: types.SimpleNamespace(close=lambda: None))


@pytest.fixture(scope="session", autouse=True)
def allow_localhost_sockets():
    """Allow localhost sockets so asyncio self-pipe and in-process comms work.

    Uses pytest-socket, if available, to restrict to loopback only.
    """
    if HAS_PYTEST_SOCKET:
        enable_socket()
        socket_allow_hosts(["127.0.0.1", "::1", "localhost"])

@pytest.fixture(autouse=True)
def mock_bluetooth():
    """Auto-mock BLE libraries (bleak, habluetooth) to prevent real BLE/socket usage in tests."""
    patches = []
    # Patch BleakClient if bleak is used
    ble_wifi_spec = importlib.util.find_spec("homeassistant.components.grid_connect.ble_wifi")
    if ble_wifi_spec is not None:
        ble_wifi = importlib.import_module("homeassistant.components.grid_connect.ble_wifi")
        patches.append(patch.object(ble_wifi, "BleakClient", AsyncMock))
    # Patch habluetooth if available
    habluetooth_spec = importlib.util.find_spec("habluetooth")
    if habluetooth_spec is not None:
        patches.append(patch("habluetooth.BluetoothClient", AsyncMock, create=True))
    # Use a single with statement for all patches
    context_managers = patches if patches else [patch("builtins.object", lambda: None)]
    with ExitStack() as stack:
        for cm in context_managers:
            stack.enter_context(cm)
        yield

@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.grid_connect.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
