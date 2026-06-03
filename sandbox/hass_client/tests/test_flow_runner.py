"""Phase 4 tests for :class:`hass_client.flow_runner.FlowRunner`.

Exercises the sandbox-side flow loop against a mock integration whose
``async_setup_entry`` is intercepted before the FlowRunner is asked to
run the flow. The wire-format assertions live here (rather than in HA
Core) because the runner's only public surface is the JSON it returns
on the channel.
"""

import asyncio
import tempfile
from types import ModuleType
from typing import Any

from hass_client._proto import sandbox_pb2 as pb
from hass_client.channel import Channel
from hass_client.codec_protobuf import ProtobufCodec
from hass_client.flow_runner import FlowRunner
from hass_client.messages import dict_to_struct, listvalue_to_list, struct_to_dict
import pytest
import voluptuous as vol

from homeassistant import config_entries as ha_config_entries, loader as ha_loader
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult


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


class _DemoFlow(ConfigFlow, domain="phase4_demo"):
    """Minimal 2-step config flow for the FlowRunner tests."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required("host"): str}),
            )
        if user_input["host"] == "bad":
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required("host"): str}),
                errors={"host": "invalid_host"},
            )
        return self.async_create_entry(
            title=f"Demo {user_input['host']}", data=user_input
        )


@pytest.fixture(name="channels")
async def _channels_fixture() -> tuple[Channel, Channel]:
    main, sandbox = _make_channel_pair()
    yield main, sandbox
    await main.close()
    await sandbox.close()


@pytest.fixture(name="runner")
async def _runner_fixture() -> FlowRunner:
    with tempfile.TemporaryDirectory(prefix="sandbox_flowrunner_") as tmp:
        runner = await FlowRunner.create(config_dir=tmp)
        # Stand up a fake "phase4_demo" integration in the loader caches
        # so async_get_flow_handler short-circuits to our registered class.
        ha_config_entries.HANDLERS["phase4_demo"] = _DemoFlow
        # Both ``phase4_demo`` and ``phase4_demo.config_flow`` must look
        # loaded for the flow-handler short-circuit to fire — see
        # ``homeassistant.config_entries._async_get_flow_handler``.
        fake_module = ModuleType("homeassistant.components.phase4_demo")
        fake_flow_module = ModuleType(
            "homeassistant.components.phase4_demo.config_flow"
        )
        runner.hass.data[ha_loader.DATA_COMPONENTS]["phase4_demo"] = fake_module
        runner.hass.data[ha_loader.DATA_COMPONENTS]["phase4_demo.config_flow"] = (
            fake_flow_module
        )
        runner.hass.config.components.add("phase4_demo")
        try:
            yield runner
        finally:
            ha_config_entries.HANDLERS.pop("phase4_demo", None)
            runner.hass.data[ha_loader.DATA_COMPONENTS].pop("phase4_demo", None)
            runner.hass.data[ha_loader.DATA_COMPONENTS].pop(
                "phase4_demo.config_flow", None
            )
            await runner.async_stop()


async def test_flow_init_returns_form(
    channels: tuple[Channel, Channel], runner: FlowRunner
) -> None:
    """flow_init drives the integration's first step and marshals the form."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    init_msg = pb.FlowInit(handler="phase4_demo")
    init_msg.context.update({"source": "user"})
    result = await main.call("sandbox/flow_init", init_msg)

    assert result.type == "form"
    assert result.step_id == "user"
    # Phase 14: data_schema rides as the same list-of-fields shape
    # voluptuous_serialize.convert produces, so the proxy on main can
    # rebuild a usable vol.Schema (or hand the list straight to the
    # frontend).
    assert listvalue_to_list(result.data_schema) == [
        {"name": "host", "type": "string", "required": True}
    ]
    assert result.has_data_schema is not True


async def test_flow_step_creates_entry(
    channels: tuple[Channel, Channel], runner: FlowRunner
) -> None:
    """flow_step with valid input ends the flow and reports CREATE_ENTRY."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    init_msg = pb.FlowInit(handler="phase4_demo")
    init_msg.context.update({"source": "user"})
    init_result = await main.call("sandbox/flow_init", init_msg)
    step_msg = pb.FlowStep(flow_id=init_result.flow_id)
    step_msg.user_input.CopyFrom(dict_to_struct({"host": "1.2.3.4"}))
    step_result = await main.call("sandbox/flow_step", step_msg)

    assert step_result.type == "create_entry"
    assert step_result.title == "Demo 1.2.3.4"
    assert struct_to_dict(step_result.data) == {"host": "1.2.3.4"}


async def test_flow_step_validation_error_returns_form(
    channels: tuple[Channel, Channel], runner: FlowRunner
) -> None:
    """A re-shown form (errors set) round-trips intact."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    init_msg = pb.FlowInit(handler="phase4_demo")
    init_msg.context.update({"source": "user"})
    init_result = await main.call("sandbox/flow_init", init_msg)
    step_msg = pb.FlowStep(flow_id=init_result.flow_id)
    step_msg.user_input.CopyFrom(dict_to_struct({"host": "bad"}))
    step_result = await main.call("sandbox/flow_step", step_msg)

    assert step_result.type == "form"
    assert struct_to_dict(step_result.errors) == {"host": "invalid_host"}


async def test_flow_init_marshals_unique_id(
    channels: tuple[Channel, Channel], runner: FlowRunner
) -> None:
    """flow_init pulls ``unique_id`` out of the live flow's context (Phase 14)."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    init_msg = pb.FlowInit(handler="phase4_demo")
    init_msg.context.update({"source": "user", "unique_id": "demo-abc"})
    result = await main.call("sandbox/flow_init", init_msg)

    assert result.type == "form"
    assert struct_to_dict(result.context).get("unique_id") == "demo-abc"


async def test_flow_abort_is_idempotent(
    channels: tuple[Channel, Channel], runner: FlowRunner
) -> None:
    """flow_abort on an unknown flow_id returns ``{}`` instead of erroring."""
    main, sandbox = channels
    runner.register(sandbox)
    main.start()
    sandbox.start()

    result = await main.call(
        "sandbox/flow_abort", pb.FlowAbort(flow_id="not-a-real-flow-id")
    )
    # FlowAbortResult is an empty message (was `result == {}` on the dict wire).
    assert isinstance(result, pb.FlowAbortResult)
    assert result.SerializeToString() == b""
