"""Real-worker config persistence and late-start integration lifecycle."""

import asyncio
import json
import os
from pathlib import Path
import sys
from textwrap import dedent
from typing import Any

import pytest

from homeassistant.components.sandbox import SandboxData
from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import SandboxBridge
from homeassistant.components.sandbox.channel import Channel
from homeassistant.components.sandbox.const import DATA_SANDBOX
from homeassistant.components.sandbox.manager import SandboxConfig, SandboxManager
from homeassistant.components.sandbox.messages import (
    decode_json_dict,
    encode_json,
    entry_to_setup_proto,
)
from homeassistant.components.sandbox.router import SandboxFlowRouter
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

DOMAIN = "sandbox_runtime_test"


@pytest.fixture
def ignore_translations_for_mock_domains() -> list[str]:
    """The synthetic integration has no translation resource."""
    return [DOMAIN]


async def test_started_worker_config_and_subentries(
    hass: HomeAssistant,
    tmp_path: Path,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Migration, refresh, ownership and reload work through a real process."""
    await hass.async_start()
    child_dir = tmp_path / "child"
    integration_dir = child_dir / "custom_components" / DOMAIN
    integration_dir.mkdir(parents=True)
    (integration_dir.parent / "__init__.py").write_text("")
    (integration_dir / "manifest.json").write_text(
        json.dumps(
            {
                "domain": DOMAIN,
                "name": "Runtime test",
                "version": "1.0.0",
                "codeowners": [],
                "requirements": [],
            }
        )
    )
    (integration_dir / "__init__.py").write_text(
        dedent("""
        import os
        from homeassistant.core import SupportsResponse, callback
        from homeassistant.helpers.start import async_at_start

        async def async_migrate_entry(hass, entry):
            hass.config_entries.async_update_entry(entry, version=2, data=entry.data | {"migrated": True})
            subentry = entry.subentries["device"]
            hass.config_entries.async_update_subentry(entry, subentry, title="Migrated device")
            return True

        async def async_setup_entry(hass, entry):
            assert hass.is_running
            await hass.config_entries.async_wait_initialized()
            started = False
            @callback
            def on_start(hass):
                nonlocal started
                started = True
            async_at_start(hass, on_start)

            async def probe(call):
                if "token" in call.data:
                    hass.config_entries.async_update_entry(entry, data=entry.data | {"token": call.data["token"]})
                return {"pid": os.getpid(), "running": hass.is_running, "started": started,
                        "data": dict(entry.data), "options": dict(entry.options),
                        "subentry_id": entry.subentries["device"].subentry_id, "subentries": {key: sub.as_dict() for key, sub in entry.subentries.items()}}
            hass.services.async_register("sandbox_runtime_test", "probe", probe, supports_response=SupportsResponse.ONLY)
            await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
            return True

        async def async_unload_entry(hass, entry):
            hass.services.async_remove("sandbox_runtime_test", "probe")
            return await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    """)
    )
    (integration_dir / "config_flow.py").write_text(
        dedent("""
        import probatio
        from homeassistant.config_entries import ConfigFlow, ConfigSubentryFlow
        class DeviceFlow(ConfigSubentryFlow):
            async def async_step_user(self, user_input=None):
                if user_input is None:
                    return self.async_show_form(step_id="user", data_schema=probatio.Schema({probatio.Required("host"): str}))
                return self.async_create_entry(title="Extra device", data=user_input, unique_id=user_input["host"])
            async def async_step_reconfigure(self, user_input=None):
                if user_input is None:
                    return self.async_show_form(step_id="reconfigure", data_schema=probatio.Schema({probatio.Required("host"): str}))
                return self.async_update_and_abort(self._get_entry(), self._get_reconfigure_subentry(), data=user_input)
        class TestFlow(ConfigFlow, domain="sandbox_runtime_test"):
            VERSION = 2
            @classmethod
            def async_get_supported_subentry_types(cls, config_entry):
                return {"device": DeviceFlow}
    """)
    )
    (integration_dir / "sensor.py").write_text(
        dedent("""
        from homeassistant.components.sensor import SensorEntity
        class TestSensor(SensorEntity):
            _attr_name = "Runtime counter"
            _attr_unique_id = "runtime-counter"
            _attr_native_value = 42
            _attr_should_poll = False
            _attr_device_info = {"identifiers": {("sandbox_runtime_test", "device")}, "name": "Device"}
        async def async_setup_entry(hass, entry, async_add_entities):
            async_add_entities([TestSensor()], config_subentry_id="device")
    """)
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        sandbox="custom",
        data={"token": "old"},
        subentries_data=[
            {
                "subentry_id": "device",
                "subentry_type": "device",
                "title": "Device",
                "unique_id": None,
                "data": {},
            }
        ],
    )
    entry.add_to_hass(hass)
    bridges: list[SandboxBridge] = []

    def on_channel(group: str, channel: Channel) -> None:
        bridge = SandboxBridge(hass, group=group, channel=channel)
        bridge.entry_sync.track(entry)
        bridges.append(bridge)

    def command(group: str, url: str) -> list[str]:
        return [
            sys.executable,
            "-c",
            "import asyncio,sys; from hass_client.sandbox import SandboxRuntime; asyncio.run(SandboxRuntime(group=sys.argv[1],url=sys.argv[2],config_dir=sys.argv[3]).run())",
            group,
            url,
            str(child_dir),
        ]

    manager = SandboxManager(
        hass,
        command_factory=command,
        on_channel_ready=on_channel,
        config=SandboxConfig(ready_timeout=10, shutdown_grace=3),
    )
    try:
        process = await manager.ensure_started("custom")
        channel = process.channel
        assert channel is not None
        request = entry_to_setup_proto(entry)
        # The fixture has already provisioned this artifact on the child.
        request.integration_source.kind = "builtin"
        result = await channel.call("sandbox/entry_setup", request, timeout=10)
        assert result.ok, result.reason
        assert entry.version == 2
        assert entry.data == {"token": "old", "migrated": True}
        assert entry.subentries["device"].title == "Migrated device"
        async with asyncio.timeout(5):
            while not (
                entities := er.async_entries_for_config_entry(
                    entity_registry, entry.entry_id
                )
            ):
                await asyncio.sleep(0.01)
        assert len(entities) == 1
        assert entities[0].config_subentry_id == "device"
        device = device_registry.async_get(entities[0].device_id)
        assert device is not None
        assert device.config_subentry_id == "device"
        assert hass.states.get(entities[0].entity_id).state == "42"

        response = await channel.call(
            "sandbox/call_service",
            pb.CallService(
                domain=DOMAIN,
                service="probe",
                service_data=encode_json({"token": "refreshed"}),
                return_response=True,
            ),
            timeout=5,
        )
        values = decode_json_dict(response.response.data)
        assert values["pid"] != os.getpid()
        assert values["running"] is True
        assert values["started"] is True
        async with asyncio.timeout(5):
            while entry.data["token"] != "refreshed":
                await asyncio.sleep(0.01)
        hass.config_entries.async_update_entry(entry, options={"poll": 60})
        await bridges[-1].entry_sync.flush()
        response = await channel.call(
            "sandbox/call_service",
            pb.CallService(domain=DOMAIN, service="probe", return_response=True),
            timeout=5,
        )
        assert decode_json_dict(response.response.data)["options"] == {"poll": 60}

        async with asyncio.timeout(5):
            while "core.config_entries" not in hass_storage:
                await asyncio.sleep(0.05)
        stored = decode_json_dict(encode_json(hass_storage["core.config_entries"]))[
            "data"
        ]
        saved = next(
            item for item in stored["entries"] if item["entry_id"] == entry.entry_id
        )
        assert saved["data"] == {"token": "refreshed", "migrated": True}
        assert saved["subentries"][0]["subentry_id"] == "device"

        result = await channel.call(
            "sandbox/entry_unload", pb.EntryUnload(entry_id=entry.entry_id), timeout=5
        )
        assert result.ok
        request = entry_to_setup_proto(entry)
        request.integration_source.kind = "builtin"
        result = await channel.call("sandbox/entry_setup", request, timeout=10)
        assert result.ok, result.reason
        response = await channel.call(
            "sandbox/call_service",
            pb.CallService(domain=DOMAIN, service="probe", return_response=True),
            timeout=5,
        )
        values = decode_json_dict(response.response.data)
        assert values["data"]["token"] == "refreshed"
        assert values["subentry_id"] == "device"

        data = SandboxData(manager=manager, bridges={"custom": bridges[-1]})
        hass.data[DATA_SANDBOX] = data
        hass.config_entries.router = SandboxFlowRouter(hass, manager, data=data)
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"), context={"source": "user"}
        )
        assert flow["type"] is FlowResultType.FORM
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"host": "new-host"}
        )
        assert flow["type"] is FlowResultType.CREATE_ENTRY
        added_id = next(key for key in entry.subentries if key != "device")
        await bridges[-1].entry_sync.flush()
        response = await channel.call(
            "sandbox/call_service",
            pb.CallService(domain=DOMAIN, service="probe", return_response=True),
            timeout=5,
        )
        assert (
            decode_json_dict(response.response.data)["subentries"][added_id][
                "unique_id"
            ]
            == "new-host"
        )
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": added_id},
        )
        assert flow["type"] is FlowResultType.FORM
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"host": "changed-host"}
        )
        assert flow["type"] is FlowResultType.ABORT
        assert flow["translation_domain"] == "homeassistant"
        assert entry.subentries[added_id].data == {"host": "changed-host"}
    finally:
        hass.config_entries.router = None
        await manager.async_graceful_shutdown_all(timeout=5)
        await manager.async_stop_all()
        for bridge in bridges:
            await bridge.async_teardown()
