"""Tests for :class:`SandboxFlowProxy` — main-side flow forwarding."""

import asyncio
from collections.abc import Iterator
import contextlib
from typing import Any, cast
from unittest.mock import patch

import pytest

from homeassistant.components.sandbox_v2.channel import Channel
from homeassistant.components.sandbox_v2.manager import SandboxManager
from homeassistant.components.sandbox_v2.router import SandboxFlowRouter
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from ._helpers import FakeSandboxManager, make_channel_pair

from tests.common import MockModule, mock_integration


class _SandboxStub:
    """Tiny sandbox-side dispatcher backed by a script of canned responses."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = responses
        self.init_calls: list[dict[str, Any]] = []
        self.step_calls: list[dict[str, Any]] = []
        self.abort_calls: list[dict[str, Any]] = []

    def attach(self, channel: Channel) -> None:
        channel.register("sandbox_v2/flow_init", self._flow_init)
        channel.register("sandbox_v2/flow_step", self._flow_step)
        channel.register("sandbox_v2/flow_abort", self._flow_abort)
        channel.register("sandbox_v2/entry_setup", self._entry_setup)
        channel.register("sandbox_v2/entry_unload", self._entry_unload)

    async def _flow_init(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.init_calls.append(payload)
        return self._pop()

    async def _flow_step(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.step_calls.append(payload)
        return self._pop()

    async def _flow_abort(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.abort_calls.append(payload)
        return {}

    async def _entry_setup(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    async def _entry_unload(self, _payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def _pop(self) -> dict[str, Any]:
        return self._responses.pop(0)


@contextlib.contextmanager
def _wired_sandbox(
    manager: FakeSandboxManager, *, group: str, responses: list[dict[str, Any]]
) -> Iterator[_SandboxStub]:
    """Wire a sandbox stub onto a fresh in-memory channel pair."""
    main_channel, sandbox_channel = make_channel_pair(
        name_a=f"main-{group}", name_b=f"sandbox-{group}"
    )
    stub = _SandboxStub(responses)
    stub.attach(sandbox_channel)
    main_channel.start()
    sandbox_channel.start()
    manager.install(group, main_channel)
    try:
        yield stub
    finally:
        # Best-effort close; the test will finish before any pending IO
        # matters, but we tag the tasks so the linter doesn't flag them.
        close_main = asyncio.ensure_future(main_channel.close())
        close_sandbox = asyncio.ensure_future(sandbox_channel.close())
        del close_main, close_sandbox


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """Suppress strings.json checks for our mock integrations."""
    return [
        "test_proxy_full",
        "test_proxy_errors",
        "test_proxy_abort",
    ]


@pytest.fixture(name="manager")
def _manager_fixture() -> FakeSandboxManager:
    """A fake sandbox manager that never spawns a subprocess."""
    return FakeSandboxManager()


async def test_full_flow_user_to_create_entry(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A user-initiated flow that asks for input then creates an entry."""
    mock_integration(hass, MockModule("test_proxy_full"))
    responses = [
        # Response to flow_init — show a form
        {
            "type": FlowResultType.FORM.value,
            "flow_id": "sandbox-flow-1",
            "handler": "test_proxy_full",
            "step_id": "user",
        },
        # Response to flow_step — create the entry
        {
            "type": FlowResultType.CREATE_ENTRY.value,
            "flow_id": "sandbox-flow-1",
            "handler": "test_proxy_full",
            "title": "Proxy Title",
            "data": {"host": "1.2.3.4"},
        },
    ]

    with (
        _wired_sandbox(manager, group="built-in", responses=responses) as stub,
        patch(
            "homeassistant.components.sandbox_v2.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "built-in"})(),
        ),
    ):
        await _install_router(hass, manager)
        result = await hass.config_entries.flow.async_init(
            "test_proxy_full", context={"source": SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Proxy Title"

    assert len(stub.init_calls) == 1
    assert stub.init_calls[0]["handler"] == "test_proxy_full"
    assert stub.init_calls[0]["context"]["source"] == SOURCE_USER
    assert stub.init_calls[0]["data"] is None
    assert len(stub.step_calls) == 1
    assert stub.step_calls[0]["flow_id"] == "sandbox-flow-1"
    assert stub.step_calls[0]["user_input"] == {"host": "1.2.3.4"}

    # The new ConfigEntry is tagged with the sandbox group via the
    # ConfigEntry.sandbox first-class field (Phase 17 — keeps the tag
    # off entry.data where integration tests assert on it).
    entries = hass.config_entries.async_entries("test_proxy_full")
    assert len(entries) == 1
    assert entries[0].sandbox == "built-in"
    assert entries[0].data == {"host": "1.2.3.4"}
    # The setup interception path marked it LOADED.
    assert entries[0].state is ConfigEntryState.LOADED


async def test_form_with_errors_reshows(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A form returned with `errors` is shown as a fresh form on main."""
    mock_integration(hass, MockModule("test_proxy_errors"))
    responses = [
        {
            "type": FlowResultType.FORM.value,
            "flow_id": "sandbox-flow-err",
            "handler": "test_proxy_errors",
            "step_id": "user",
        },
        {
            "type": FlowResultType.FORM.value,
            "flow_id": "sandbox-flow-err",
            "handler": "test_proxy_errors",
            "step_id": "user",
            "errors": {"host": "invalid_host"},
        },
    ]

    with (
        _wired_sandbox(manager, group="built-in", responses=responses),
        patch(
            "homeassistant.components.sandbox_v2.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "built-in"})(),
        ),
    ):
        await _install_router(hass, manager)
        result = await hass.config_entries.flow.async_init(
            "test_proxy_errors", context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "bad"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"host": "invalid_host"}


async def test_abort_is_propagated(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """An ABORT from the sandbox surfaces as an abort on main."""
    mock_integration(hass, MockModule("test_proxy_abort"))
    responses = [
        {
            "type": FlowResultType.ABORT.value,
            "flow_id": "sandbox-flow-abort",
            "handler": "test_proxy_abort",
            "reason": "already_configured",
        }
    ]

    with (
        _wired_sandbox(manager, group="custom", responses=responses),
        patch(
            "homeassistant.components.sandbox_v2.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "custom"})(),
        ),
    ):
        await _install_router(hass, manager)
        result = await hass.config_entries.flow.async_init(
            "test_proxy_abort", context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _install_router(hass: HomeAssistant, manager: FakeSandboxManager) -> None:
    """Attach a router that uses ``manager`` to ``hass.config_entries``."""
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))
    hass.config_entries.router = router
