"""Schema bridging, unique_id propagation, and the unload hook.

Covers four pieces:

* The serialised :class:`vol.Schema` bridge for flow forms and mirrored
  services (the proxy reconstructs a usable schema from the wire shape).
* ``unique_id`` propagation from the sandbox flow's ``context`` to the
  proxy's ``self.context``, so main's duplicate-detection fires.
* The ``ConfigEntryRouter.async_unload_entry`` hook on
  :class:`ConfigEntries.async_unload`.
"""

import asyncio
from collections.abc import Iterator
import contextlib
from typing import Any, cast
from unittest.mock import patch

import pytest
import voluptuous as vol
import voluptuous_serialize

from homeassistant import data_entry_flow
from homeassistant.components.sandbox import schema_bridge
from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import SandboxBridge
from homeassistant.components.sandbox.channel import Channel
from homeassistant.components.sandbox.manager import SandboxManager
from homeassistant.components.sandbox.messages import struct_to_dict
from homeassistant.components.sandbox.router import SandboxFlowRouter
from homeassistant.components.sandbox.schema_bridge import reconstruct_schema
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.helpers import config_validation as cv, selector

from ._helpers import FakeSandboxManager, make_channel_pair

from tests.common import MockConfigEntry, MockModule, mock_integration


class _SandboxStub:
    """Tiny script-driven sandbox dispatcher for proxy-flow tests."""

    def __init__(self, responses: list[pb.FlowResult]) -> None:
        self._responses = responses
        self.init_calls: list[pb.FlowInit] = []
        self.step_calls: list[pb.FlowStep] = []
        self.unload_calls: list[pb.EntryUnload] = []

    def attach(self, channel: Channel) -> None:
        channel.register("sandbox/flow_init", self._flow_init)
        channel.register("sandbox/flow_step", self._flow_step)
        channel.register("sandbox/flow_abort", self._flow_abort)
        channel.register("sandbox/entry_setup", self._entry_setup)
        channel.register("sandbox/entry_unload", self._entry_unload)

    async def _flow_init(self, payload: pb.FlowInit) -> pb.FlowResult:
        self.init_calls.append(payload)
        return self._pop()

    async def _flow_step(self, payload: pb.FlowStep) -> pb.FlowResult:
        self.step_calls.append(payload)
        return self._pop()

    async def _flow_abort(self, _payload: pb.FlowAbort) -> pb.FlowAbortResult:
        return pb.FlowAbortResult()

    async def _entry_setup(self, _payload: pb.EntrySetup) -> pb.EntrySetupResult:
        return pb.EntrySetupResult(ok=True)

    async def _entry_unload(self, payload: pb.EntryUnload) -> pb.EntryUnloadResult:
        self.unload_calls.append(payload)
        return pb.EntryUnloadResult(ok=True)

    def _pop(self) -> pb.FlowResult:
        return self._responses.pop(0)


@contextlib.contextmanager
def _wired_sandbox(
    manager: FakeSandboxManager, *, group: str, responses: list[pb.FlowResult]
) -> Iterator[_SandboxStub]:
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
        close_main = asyncio.ensure_future(main_channel.close())
        close_sandbox = asyncio.ensure_future(sandbox_channel.close())
        del close_main, close_sandbox


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """Suppress strings.json checks for the mock domains."""
    return [
        "mock_schema",
        "mock_unique",
        "mock_duplicate",
        "mock_unload",
        "mock_local",
        "mock_svc",
    ]


@pytest.fixture(name="manager")
def _manager_fixture() -> FakeSandboxManager:
    return FakeSandboxManager()


async def _install_router(hass: HomeAssistant, manager: FakeSandboxManager) -> None:
    router = SandboxFlowRouter(hass, cast(SandboxManager, manager))
    hass.config_entries.router = router


# ---------------------------------------------------------------------------
# 1. Schema bridge — flow form
# ---------------------------------------------------------------------------


def test_reconstruct_schema_round_trips_primitive_types() -> None:
    """A primitive serialised schema reconstructs into a usable vol.Schema."""
    serialized = [
        {"name": "host", "type": "string", "required": True},
        {"name": "port", "type": "integer", "required": False, "default": 8080},
    ]

    schema = reconstruct_schema(serialized)
    assert schema is not None

    # Good input passes; default for the optional key gets applied.
    valid = schema({"host": "1.2.3.4"})
    assert valid == {"host": "1.2.3.4", "port": 8080}

    # Missing required key is rejected.
    with pytest.raises(vol.Invalid):
        schema({"port": 1234})


def test_reconstruct_schema_handles_select_options() -> None:
    """A serialised ``select`` becomes a ``vol.In`` that gates membership."""
    schema = reconstruct_schema(
        [
            {
                "name": "mode",
                "type": "select",
                "required": True,
                "options": [["fast", "Fast"], ["slow", "Slow"]],
            }
        ]
    )
    assert schema is not None
    assert schema({"mode": "fast"}) == {"mode": "fast"}
    with pytest.raises(vol.Invalid):
        schema({"mode": "nope"})


def test_reconstruct_schema_round_trips_selectors_and_sections() -> None:
    """Selectors + a section survive serialize → reconstruct → re-serialize.

    The flow manager re-serialises main's reconstructed schema for the
    frontend, so the reconstruction must reproduce the sandbox's original
    list verbatim — otherwise selectors degrade to plain text boxes.
    """
    original = vol.Schema(
        {
            vol.Required("mode"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=["fast", "slow"])
            ),
            vol.Optional("count", default=5): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=10)
            ),
            vol.Required("advanced"): data_entry_flow.section(
                vol.Schema(
                    {
                        vol.Optional("retries", default=3): selector.NumberSelector(
                            selector.NumberSelectorConfig(min=1, max=5)
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )

    serialized = voluptuous_serialize.convert(
        original, custom_serializer=cv.custom_serializer
    )
    reconstructed = reconstruct_schema(serialized)
    assert reconstructed is not None
    re_serialized = voluptuous_serialize.convert(
        reconstructed, custom_serializer=cv.custom_serializer
    )

    # Round-trip is lossless: the re-serialised list equals the original.
    assert re_serialized == serialized
    # And the selector/section types survived (not collapsed to passthrough).
    by_name = {entry["name"]: entry for entry in re_serialized}
    assert "selector" in by_name["mode"]
    assert "select" in by_name["mode"]["selector"]
    assert "selector" in by_name["count"]
    assert by_name["advanced"]["type"] == "expandable"
    assert by_name["advanced"]["expanded"] is False


async def test_flow_form_renders_reconstructed_schema(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A FORM with a serialised data_schema arrives on main with the schema."""
    mock_integration(hass, MockModule("mock_schema"))
    serialized_schema = [
        {"name": "host", "type": "string", "required": True},
    ]
    form = pb.FlowResult(
        type=FlowResultType.FORM.value,
        flow_id="sandbox-flow-schema",
        handler="mock_schema",
        step_id="user",
    )
    form.data_schema.extend(serialized_schema)
    responses = [form]

    with (
        _wired_sandbox(manager, group="built-in", responses=responses),
        patch(
            "homeassistant.components.sandbox.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "built-in"})(),
        ),
    ):
        await _install_router(hass, manager)
        result = await hass.config_entries.flow.async_init(
            "mock_schema", context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    assert schema is not None
    # Schema actually validates: empty input is rejected.
    with pytest.raises(vol.Invalid):
        schema({})
    assert schema({"host": "1.2.3.4"}) == {"host": "1.2.3.4"}


# ---------------------------------------------------------------------------
# 2. Schema bridge — service registration
# ---------------------------------------------------------------------------


async def test_register_service_with_schema_validates_on_main(
    hass: HomeAssistant,
) -> None:
    """Sandbox-mirrored service uses its reconstructed schema on main calls."""
    MockConfigEntry(domain="mock_svc", title="Mock", sandbox="built-in").add_to_hass(
        hass
    )
    main_channel, sandbox_channel = make_channel_pair(
        name_a="main-mock", name_b="sandbox-mock"
    )
    bridge = SandboxBridge(hass, group="built-in", channel=main_channel)
    main_channel.start()
    sandbox_channel.start()

    seen: list[pb.CallService] = []

    async def _on_call_service(payload: pb.CallService) -> Any:
        seen.append(payload)
        return None

    sandbox_channel.register("sandbox/call_service", _on_call_service)

    schema_payload = [
        {"name": "host", "type": "string", "required": True},
    ]

    register_service = pb.RegisterService(
        domain="mock_svc",
        service="do_thing",
        supports_response="none",
    )
    register_service.schema.extend(schema_payload)

    try:
        result = await sandbox_channel.call(
            "sandbox/register_service", register_service
        )
        assert result.installed is True

        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "mock_svc", "do_thing", {"wrong": "field"}, blocking=True
            )
        assert seen == []

        await hass.services.async_call(
            "mock_svc", "do_thing", {"host": "1.2.3.4"}, blocking=True
        )
        assert len(seen) == 1
        assert struct_to_dict(seen[0].service_data) == {"host": "1.2.3.4"}
    finally:
        await main_channel.close()
        await sandbox_channel.close()
        del bridge


# ---------------------------------------------------------------------------
# 3. unique_id propagation
# ---------------------------------------------------------------------------


async def test_unique_id_propagates_to_proxy_context(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A sandbox-side ``unique_id`` is mirrored onto the proxy's context."""
    mock_integration(hass, MockModule("mock_unique"))
    form = pb.FlowResult(
        type=FlowResultType.FORM.value,
        flow_id="sandbox-flow-uid",
        handler="mock_unique",
        step_id="user",
    )
    form.context.update({"source": SOURCE_USER, "unique_id": "abc-123"})
    responses = [form]

    with (
        _wired_sandbox(manager, group="built-in", responses=responses),
        patch(
            "homeassistant.components.sandbox.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "built-in"})(),
        ),
    ):
        await _install_router(hass, manager)
        result = await hass.config_entries.flow.async_init(
            "mock_unique", context={"source": SOURCE_USER}
        )
        # The framework now reads unique_id off the proxy's context;
        # ``async_progress_by_handler`` surfaces it for duplicate checks.
        progress = hass.config_entries.flow.async_progress_by_handler("mock_unique")

    assert result["type"] is FlowResultType.FORM
    assert len(progress) == 1
    assert progress[0]["context"].get("unique_id") == "abc-123"


async def test_duplicate_unique_id_aborts_second_flow(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """A second flow with the same propagated unique_id aborts on main."""
    mock_integration(hass, MockModule("mock_duplicate"))
    form_a = pb.FlowResult(
        type=FlowResultType.FORM.value,
        flow_id="sandbox-flow-dup-a",
        handler="mock_duplicate",
        step_id="user",
    )
    form_a.context.update({"source": SOURCE_USER, "unique_id": "dup-1"})
    responses_a = [form_a]
    form_b = pb.FlowResult(
        type=FlowResultType.FORM.value,
        flow_id="sandbox-flow-dup-b",
        handler="mock_duplicate",
        step_id="user",
    )
    form_b.context.update({"source": SOURCE_USER, "unique_id": "dup-1"})
    responses_b = [form_b]

    with (
        _wired_sandbox(manager, group="built-in", responses=responses_a + responses_b),
        patch(
            "homeassistant.components.sandbox.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "built-in"})(),
        ),
    ):
        await _install_router(hass, manager)
        first = await hass.config_entries.flow.async_init(
            "mock_duplicate", context={"source": SOURCE_USER}
        )
        # The framework's duplicate-detection guard fires inside the
        # second `async_init`. See `_check_in_progress_by_unique_id`.
        try:
            second = await hass.config_entries.flow.async_init(
                "mock_duplicate", context={"source": SOURCE_USER}
            )
        except AbortFlow as err:
            second = {
                "type": FlowResultType.ABORT,
                "reason": err.reason,
            }

    assert first["type"] is FlowResultType.FORM
    # AbortFlow OR an ABORT result both signal the duplicate was caught;
    # which one bubbles up depends on whether the proxy's first step
    # finishes before the second async_init runs the guard.
    assert second["type"] is FlowResultType.ABORT


# ---------------------------------------------------------------------------
# 4. async_unload_entry core hook
# ---------------------------------------------------------------------------


async def test_async_unload_consults_router_for_sandboxed_entry(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """ConfigEntries.async_unload calls the router for sandbox-tagged entries."""
    mock_integration(hass, MockModule("mock_unload"))
    with (
        _wired_sandbox(manager, group="built-in", responses=[]) as stub,
        patch(
            "homeassistant.components.sandbox.router.classify",
            return_value=type("A", (), {"is_main": False, "group": "built-in"})(),
        ),
    ):
        await _install_router(hass, manager)
        entry = MockConfigEntry(
            domain="mock_unload",
            data={"host": "1.2.3.4"},
            sandbox="built-in",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        assert entry.state is ConfigEntryState.LOADED

        unloaded = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert unloaded is True
    assert entry.state is ConfigEntryState.NOT_LOADED
    # The sandbox saw exactly one entry_unload call.
    assert len(stub.unload_calls) == 1
    assert stub.unload_calls[0].entry_id == entry.entry_id


async def test_async_unload_falls_through_for_non_sandboxed_entry(
    hass: HomeAssistant, manager: FakeSandboxManager
) -> None:
    """The router returns None for plain entries — normal unload runs."""

    async def _async_unload_entry(_hass: HomeAssistant, _entry: Any) -> bool:
        return True

    mock_integration(
        hass,
        MockModule("mock_local", async_unload_entry=_async_unload_entry),
    )
    await _install_router(hass, manager)

    entry = MockConfigEntry(domain="mock_local", data={"host": "1.2.3.4"})
    entry.add_to_hass(hass)
    # Mark loaded directly; we're not exercising async_setup here.
    entry.mock_state(hass, ConfigEntryState.LOADED)

    unloaded = await hass.config_entries.async_unload(entry.entry_id)
    assert unloaded is True
    assert entry.state is ConfigEntryState.NOT_LOADED


# ---------------------------------------------------------------------------
# Reconstruct edge cases
# ---------------------------------------------------------------------------


def test_reconstruct_schema_returns_none_for_empty() -> None:
    """``None`` / empty list short-circuit to ``None`` (no schema)."""
    assert reconstruct_schema(None) is None
    assert reconstruct_schema([]) is None


def test_reconstruct_schema_falls_back_to_passthrough() -> None:
    """Unknown field types accept any value — sandbox does the real check."""
    schema = reconstruct_schema(
        [{"name": "blob", "type": "magic-future-type", "required": True}]
    )
    assert schema is not None
    # The pass-through accepts arbitrary data: the sandbox-side handler
    # runs the real validator, so a permissive main-side gate is fine.
    assert schema({"blob": {"any": "shape"}}) == {"blob": {"any": "shape"}}


def test_reconstruct_schema_only_exposes_public_api() -> None:
    """schema_bridge keeps a tight public surface (one function)."""
    assert schema_bridge.__all__ == ["reconstruct_schema"]
