"""Exercise native Shelly entities using real inbound RPC transport."""

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any
from unittest.mock import patch

from aiohttp import WSMessage, WSMsgType
from aioshelly.json import json_dumps, json_loads
from aioshelly.rpc_device import RpcDevice
import pytest
from yarl import URL

from homeassistant.components.shelly.const import (
    CONF_CONNECTION_TYPE,
    CONF_GEN,
    CONF_REMOTE_CREDENTIAL,
    CONF_SLEEP_PERIOD,
    CONNECTION_REMOTE_WS,
    DOMAIN,
    EVENT_SHELLY_CLICK,
    OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID,
)
from homeassistant.components.shelly.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.shelly.remote_connection import RemoteConnectionManager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_EXTERNAL_URL,
    CONF_MODEL,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from .test_remote import DEVICE_INFO, make_request

from tests.common import MockConfigEntry, async_capture_events

REAL_CREATE = RpcDevice.create


def notify_loaded(entry: MockConfigEntry, event: asyncio.Event) -> None:
    """Wake a test waiting for setup, ignoring intermediate state changes."""
    if entry.state is ConfigEntryState.LOADED:
        event.set()


class RemoteShellySocket:
    """Respond to RPC requests through an asynchronous WebSocket receive queue."""

    def __init__(self, url: str) -> None:
        """Initialize a minimal mains-powered Shelly switch."""
        self.closed = False
        self.queue: asyncio.Queue[WSMessage] = asyncio.Queue()
        self.calls: list[dict[str, Any]] = []
        self.config = {
            "sys": {"device": {"name": "Remote relay"}, "ui_data": {}},
            "wifi": {"sta": {"enable": True}, "sta1": {"enable": False}},
            "ws": {"enable": True, "server": url},
            "switch:0": {"id": 0, "name": "Relay"},
            "input:0": {"id": 0, "type": "switch", "enable": True},
        }
        self.status = {
            "sys": {"wakeup_period": 0, "available_updates": {}},
            "wifi": {"rssi": -55, "sta_ip": "192.168.99.5"},
            "switch:0": {"id": 0, "output": False, "source": "WS_in"},
            "input:0": {"id": 0, "state": False},
        }

    async def prepare(self, request: Any) -> None:
        """Accept the already authenticated test request."""

    async def send_json(self, frame: dict[str, Any]) -> None:
        """Respond to the endpoint's identity query."""
        await self.respond(frame)

    async def send_frame(self, data: bytes, opcode: WSMsgType) -> None:
        """Respond to an actual transport request."""
        await self.respond(json_loads(data))

    async def respond(self, frame: dict[str, Any]) -> None:
        """Return device data, recording every outgoing request."""
        self.calls.append(frame)
        responses = {
            "Shelly.GetDeviceInfo": DEVICE_INFO,
            "Shelly.GetConfig": self.config,
            "Shelly.GetStatus": self.status,
            "Shelly.GetComponents": {"total": 0, "components": []},
            "Shelly.ListMethods": {"methods": ["Switch.Set"]},
            "Switch.Set": {},
        }
        self.notify({"id": frame["id"], "result": deepcopy(responses[frame["method"]])})

    def notify(self, frame: dict[str, Any]) -> None:
        """Enqueue a response or unsolicited notification."""
        self.queue.put_nowait(
            WSMessage(
                WSMsgType.TEXT, json_dumps({"src": DEVICE_INFO["id"], **frame}), ""
            )
        )

    async def receive(self) -> WSMessage:
        """Receive the next queued WebSocket message."""
        return await self.queue.get()

    async def __aiter__(self) -> AsyncIterator[WSMessage]:
        """Receive messages until the peer closes."""
        while not self.closed:
            message = await self.receive()
            if message.type is WSMsgType.CLOSED:
                return
            yield message

    async def close(self, *, code: int = 1000) -> None:
        """Close the connection and wake its receiver."""
        self.closed = True
        self.queue.put_nowait(WSMessage(WSMsgType.CLOSED, None, ""))


async def test_remote_native_credential_rotation(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify rotation through real admission, RPC, persistence and native control."""
    monkeypatch.setattr(RpcDevice, "create", REAL_CREATE)
    manager = RemoteConnectionManager(hass)
    old_record, old_url = manager.create_credential(URL("https://ha.example.com"))
    old_socket = RemoteShellySocket(old_url)
    with (
        patch(
            "homeassistant.components.shelly.async_get_remote_manager",
            return_value=manager,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_get_remote_manager",
            return_value=manager,
        ),
        patch(
            "homeassistant.components.shelly.remote_connection.web.WebSocketResponse",
            return_value=old_socket,
        ),
    ):
        old_handler = hass.async_create_background_task(
            manager.accept(make_request(URL(old_url).query["remote_key"]), old_record),
            "Test original device credential",
            eager_start=True,
        )
        await old_record.ready.wait()
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DEVICE_INFO["mac"],
            minor_version=3,
            data={
                CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
                CONF_REMOTE_CREDENTIAL: old_record.digest,
                CONF_GEN: 2,
                CONF_MODEL: DEVICE_INFO["model"],
                CONF_SLEEP_PERIOD: 0,
            },
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        device = entry.runtime_data.rpc.device
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        switch = next(
            entity.entity_id for entity in entities if entity.domain == "switch"
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "remote_regenerate"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EXTERNAL_URL: "https://ha.example.com"}
        )
        url = result["description_placeholders"]["connection_url"]
        record = manager.lookup(URL(url).query["remote_key"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["errors"] == {"base": "cannot_connect"}
        assert entry.data[CONF_REMOTE_CREDENTIAL] == old_record.digest
        assert not old_socket.closed
        candidate = RemoteShellySocket(url)
        with patch(
            "homeassistant.components.shelly.remote_connection.web.WebSocketResponse",
            return_value=candidate,
        ):
            handler = hass.async_create_background_task(
                manager.accept(make_request(URL(url).query["remote_key"]), record),
                "Test replacement device credential",
                eager_start=True,
            )
            await record.ready.wait()
            await hass.async_block_till_done()
            assert entry.runtime_data.rpc._connect_task is not None
            await entry.runtime_data.rpc._connect_task
            assert manager.lookup(URL(old_url).query["remote_key"]) is old_record
            candidate.calls.clear()
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {}
            )
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "reconfigure_successful"
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            assert entry.runtime_data.rpc.device is device
            assert entry.data[CONF_REMOTE_CREDENTIAL] == record.digest
            assert record.expires_at is None
            assert manager.lookup(URL(old_url).query["remote_key"]) is None
            assert manager.lookup(URL(url).query["remote_key"]) is record
            assert old_socket.closed
            assert not candidate.closed
            assert {"Shelly.GetConfig", "Shelly.GetStatus"}.issubset(
                {call["method"] for call in candidate.calls}
            )
            assert (
                er.async_entries_for_config_entry(entity_registry, entry.entry_id)
                == entities
            )
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": switch}, blocking=True
            )
            assert candidate.calls[-1]["method"] == "Switch.Set"
            assert URL(url).query["remote_key"] not in repr(entry.as_dict())
            await hass.config_entries.async_unload(entry.entry_id)
            await candidate.close()
            await handler
        await old_handler


async def test_remote_regeneration_restores_revoked_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A verified replacement resumes native setup after access was revoked."""
    monkeypatch.setattr(RpcDevice, "create", REAL_CREATE)
    manager = RemoteConnectionManager(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_INFO["mac"],
        minor_version=3,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: None,
            CONF_GEN: 2,
            CONF_MODEL: DEVICE_INFO["model"],
            CONF_SLEEP_PERIOD: 0,
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.shelly.async_get_remote_manager",
            return_value=manager,
        ),
        patch(
            "homeassistant.components.shelly.config_flow.async_get_remote_manager",
            return_value=manager,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        assert entry.state is ConfigEntryState.SETUP_RETRY
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "remote_regenerate"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EXTERNAL_URL: "https://ha.example.com"}
        )
        url = result["description_placeholders"]["connection_url"]
        record = manager.lookup(URL(url).query["remote_key"])
        candidate = RemoteShellySocket(url)
        with patch(
            "homeassistant.components.shelly.remote_connection.web.WebSocketResponse",
            return_value=candidate,
        ):
            handler = hass.async_create_background_task(
                manager.accept(make_request(URL(url).query["remote_key"]), record),
                "Test replacement for revoked credential",
                eager_start=True,
            )
            await record.ready.wait()
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.SETUP_RETRY
            loaded = asyncio.Event()
            unsubscribe = entry.async_on_state_change(
                lambda: notify_loaded(entry, loaded)
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {}
            )
            assert result["type"] is FlowResultType.ABORT
            assert result["reason"] == "reconfigure_successful"
            await asyncio.wait_for(loaded.wait(), 5)
            unsubscribe()
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            assert entry.runtime_data.rpc.device.connected
            assert entry.data[CONF_REMOTE_CREDENTIAL] == record.digest
            assert record.expires_at is None
            assert not candidate.closed
            assert URL(url).query["remote_key"] not in repr(entry.as_dict())
            await hass.config_entries.async_unload(entry.entry_id)
            await handler


async def test_remote_native_entities_and_reconnect(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Use native entities, preserve identity and resync after an Internet outage."""
    monkeypatch.setattr(RpcDevice, "create", REAL_CREATE)
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    socket = RemoteShellySocket(url)
    with (
        patch(
            "homeassistant.components.shelly.async_get_remote_manager",
            return_value=manager,
        ),
        patch(
            "homeassistant.components.shelly.remote_connection.web.WebSocketResponse",
            return_value=socket,
        ),
    ):
        handler = hass.async_create_background_task(
            manager.accept(make_request(URL(url).query["remote_key"]), record),
            "Test remote device",
            eager_start=True,
        )
        await record.ready.wait()
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=DEVICE_INFO["mac"],
            title="Remote relay",
            minor_version=3,
            data={
                CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
                CONF_REMOTE_CREDENTIAL: record.digest,
                CONF_GEN: 2,
                CONF_MODEL: DEVICE_INFO["model"],
                CONF_SLEEP_PERIOD: 0,
            },
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = entry.runtime_data.rpc
        device = coordinator.device
        assert isinstance(device, RpcDevice)
        assert device.options.ip_address is None
        assert device.aiohttp_session is None
        assert Platform.CAMERA not in entry.runtime_data.platforms
        assert coordinator.configuration_url is None
        assert (
            issue_registry.async_get_issue(
                DOMAIN,
                OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID.format(
                    unique=entry.unique_id
                ),
            )
            is None
        )
        device._last_error = ValueError(url)
        with patch(
            "homeassistant.components.shelly.diagnostics.async_get_remote_manager",
            return_value=manager,
        ):
            diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        assert URL(url).query["remote_key"] not in repr(diagnostics)
        assert record.digest not in repr(diagnostics)
        assert diagnostics["transport"]["connected"] is True
        assert diagnostics["device_settings"]["ws_outbound_server_valid"] is True
        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        switch = next(
            entity.entity_id for entity in entities if entity.domain == "switch"
        )
        assert hass.states.get(switch).state == STATE_OFF
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
        assert socket.calls[-1]["method"] == "Switch.Set"
        assert socket.calls[-1]["params"] == {"id": 0, "on": True}
        socket.notify(
            {"method": "NotifyStatus", "params": {"switch:0": {"output": True}}}
        )
        await hass.async_block_till_done()
        assert hass.states.get(switch).state == STATE_ON
        clicks = async_capture_events(hass, EVENT_SHELLY_CLICK)
        socket.notify(
            {
                "method": "NotifyEvent",
                "params": {
                    "events": [
                        {"component": "input:0", "id": 0, "event": "single_push"}
                    ]
                },
            }
        )
        await hass.async_block_till_done()
        assert len(clicks) == 1

        await socket.close()
        await handler
        await hass.async_block_till_done()
        assert hass.states.get(switch).state == STATE_UNAVAILABLE
        replacement = RemoteShellySocket(url)
        with patch(
            "homeassistant.components.shelly.remote_connection.web.WebSocketResponse",
            return_value=replacement,
        ):
            handler = hass.async_create_background_task(
                manager.accept(make_request(URL(url).query["remote_key"]), record),
                "Test reconnected device",
                eager_start=True,
            )
            await hass.async_block_till_done()
            assert coordinator._connect_task is not None
            await coordinator._connect_task
            await hass.async_block_till_done()
            assert entry.runtime_data.rpc.device is device
            assert hass.states.get(switch).state == STATE_OFF
            assert record.reconnect_count == 1
            assert (
                er.async_entries_for_config_entry(entity_registry, entry.entry_id)
                == entities
            )
            assert (
                dr.async_entries_for_config_entry(device_registry, entry.entry_id)
                == devices
            )
            await hass.services.async_call(
                "switch", "turn_on", {"entity_id": switch}, blocking=True
            )
            assert replacement.calls[-1]["method"] == "Switch.Set"
            await hass.config_entries.async_unload(entry.entry_id)
            await handler


async def test_remote_setup_resumes_when_device_connects(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restore a hash-only entry at HA startup and resume setup on its first socket."""
    monkeypatch.setattr(RpcDevice, "create", REAL_CREATE)
    manager = RemoteConnectionManager(hass)
    record, url = manager.create_credential(URL("https://ha.example.com"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_INFO["mac"],
        title="Remote relay",
        minor_version=3,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_REMOTE_WS,
            CONF_REMOTE_CREDENTIAL: record.digest,
            CONF_GEN: 2,
            CONF_MODEL: DEVICE_INFO["model"],
            CONF_SLEEP_PERIOD: 0,
        },
    )
    entry.add_to_hass(hass)
    socket = RemoteShellySocket(url)
    with (
        patch(
            "homeassistant.components.shelly.async_get_remote_manager",
            return_value=manager,
        ),
        patch(
            "homeassistant.components.shelly.remote_connection.web.WebSocketResponse",
            return_value=socket,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        assert entry.state is ConfigEntryState.SETUP_RETRY
        loaded = asyncio.Event()
        unsubscribe = entry.async_on_state_change(lambda: notify_loaded(entry, loaded))
        handler = hass.async_create_background_task(
            manager.accept(make_request(URL(url).query["remote_key"]), record),
            "Test restored remote device",
            eager_start=True,
        )
        await asyncio.wait_for(loaded.wait(), 5)
        assert entry.state is ConfigEntryState.LOADED
        unsubscribe()
        await hass.async_block_till_done()
        assert entry.runtime_data.rpc.device.connected
        assert entry.runtime_data.rpc.device.options.ip_address is None
        await hass.config_entries.async_unload(entry.entry_id)
        await handler
