"""Test the Z-Wave JS init module."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonsOptions
import pytest
from zwave_js_server.client import Client
from zwave_js_server.const import SecurityClass
from zwave_js_server.event import Event
from zwave_js_server.exceptions import (
    BaseZwaveJSServerError,
    InvalidServerVersion,
    NotConnected,
)
from zwave_js_server.model.controller import ProvisioningEntry
from zwave_js_server.model.node import Node, NodeDataType
from zwave_js_server.model.version import VersionInfo

from homeassistant.components.hassio import HassioAPIError
from homeassistant.components.persistent_notification import async_dismiss
from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.helpers import get_device_id, get_device_id_ext
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from .common import (
    AIR_TEMPERATURE_SENSOR,
    BULB_6_MULTI_COLOR_LIGHT_ENTITY,
    EATON_RF9640_ENTITY,
)

from tests.common import (
    MockConfigEntry,
    async_call_logger_set_level,
    async_fire_time_changed,
    async_get_persistent_notifications,
)
from tests.typing import WebSocketGenerator

CONTROLLER_PATCH_PREFIX = "zwave_js_server.model.controller.Controller"


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture() -> Generator[int]:
    """Mock the connect timeout."""
    with patch("homeassistant.components.zwave_js.CONNECT_TIMEOUT", new=0) as timeout:
        yield timeout


async def test_entry_setup_unload(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the integration set up and unload."""
    entry = integration

    assert client.connect.call_count == 1
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert client.disconnect.call_count == 1
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("integration")
async def test_home_assistant_stop(
    hass: HomeAssistant,
    client: MagicMock,
) -> None:
    """Test we clean up on home assistant stop."""
    await hass.async_stop()

    assert client.disconnect.call_count == 1


@pytest.mark.usefixtures("client", "connect_timeout")
async def test_initialized_timeout(hass: HomeAssistant) -> None:
    """Test we handle a timeout during client initialization."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("client")
async def test_enabled_statistics(hass: HomeAssistant) -> None:
    """Test that we enabled statistics if the entry is opted in."""
    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": True},
    )
    entry.add_to_hass(hass)

    with patch(
        "zwave_js_server.model.driver.Driver.async_enable_statistics"
    ) as mock_cmd:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_cmd.called


@pytest.mark.usefixtures("client")
async def test_disabled_statistics(hass: HomeAssistant) -> None:
    """Test that we disabled statistics if the entry is opted out."""
    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": False},
    )
    entry.add_to_hass(hass)

    with patch(
        "zwave_js_server.model.driver.Driver.async_disable_statistics"
    ) as mock_cmd:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert mock_cmd.called


@pytest.mark.usefixtures("client")
async def test_noop_statistics(hass: HomeAssistant) -> None:
    """Test that we don't make statistics calls if user hasn't set preference."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    with (
        patch(
            "zwave_js_server.model.driver.Driver.async_enable_statistics"
        ) as mock_cmd1,
        patch(
            "zwave_js_server.model.driver.Driver.async_disable_statistics"
        ) as mock_cmd2,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not mock_cmd1.called
        assert not mock_cmd2.called


async def test_driver_ready_timeout_during_setup(
    hass: HomeAssistant,
    client: MagicMock,
    listen_block: asyncio.Event,
) -> None:
    """Test we handle driver ready timeout during setup."""

    async def listen(driver_ready: asyncio.Event) -> None:
        """Mock listen."""
        await listen_block.wait()

    client.listen.side_effect = listen

    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": True},
    )
    entry.add_to_hass(hass)
    assert client.disconnect.call_count == 0

    with patch("homeassistant.components.zwave_js.DRIVER_READY_TIMEOUT", new=0):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize("core_state", [CoreState.running, CoreState.stopping])
@pytest.mark.parametrize(
    ("listen_future_result_method", "listen_future_result"),
    [
        ("set_exception", BaseZwaveJSServerError("Boom")),
        ("set_exception", Exception("Boom")),
        ("set_result", None),
    ],
)
async def test_listen_done_during_setup_before_forward_entry(
    hass: HomeAssistant,
    client: MagicMock,
    listen_block: asyncio.Event,
    core_state: CoreState,
    listen_future_result_method: str,
    listen_future_result: Exception | None,
) -> None:
    """Test listen task finishing during setup before forward entry."""
    listen_result = asyncio.Future[None]()
    assert hass.state is CoreState.running

    async def connect():
        await asyncio.sleep(0)
        client.connected = True

    async def listen(driver_ready: asyncio.Event) -> None:
        await listen_block.wait()
        await listen_result
        async_fire_time_changed(hass, fire_all=True)

    client.connect.side_effect = connect
    client.listen.side_effect = listen
    hass.set_state(core_state)
    listen_block.set()
    getattr(listen_result, listen_future_result_method)(listen_future_result)

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    assert client.disconnect.call_count == 0

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert client.disconnect.call_count == 1


async def test_not_connected_during_setup_after_forward_entry(
    hass: HomeAssistant,
    client: MagicMock,
    listen_block: asyncio.Event,
) -> None:
    """Test we handle not connected client during setup after forward entry."""
    listen_result = asyncio.Future[None]()

    async def send_command_side_effect(*args: Any, **kwargs: Any) -> None:
        """Mock send command."""
        listen_block.set()
        listen_result.set_result(None)
        # Yield to allow the listen task to run
        await asyncio.sleep(0)
        raise NotConnected("Boom")

    async def listen(driver_ready: asyncio.Event) -> None:
        """Mock listen."""
        driver_ready.set()
        client.async_send_command.side_effect = send_command_side_effect
        await listen_block.wait()
        await listen_result

    client.listen.side_effect = listen

    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": True},
    )
    entry.add_to_hass(hass)
    assert client.disconnect.call_count == 0

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize("core_state", [CoreState.running, CoreState.stopping])
@pytest.mark.parametrize(
    ("listen_future_result_method", "listen_future_result"),
    [
        ("set_exception", BaseZwaveJSServerError("Boom")),
        ("set_exception", Exception("Boom")),
        ("set_result", None),
    ],
)
async def test_listen_done_during_setup_after_forward_entry(
    hass: HomeAssistant,
    client: MagicMock,
    listen_block: asyncio.Event,
    core_state: CoreState,
    listen_future_result_method: str,
    listen_future_result: Exception | None,
) -> None:
    """Test listen task finishing during setup after forward entry."""
    listen_result = asyncio.Future[None]()
    assert hass.state is CoreState.running

    original_send_command_side_effect = client.async_send_command.side_effect

    async def send_command_side_effect(*args: Any, **kwargs: Any) -> None:
        """Mock send command."""
        listen_block.set()
        getattr(listen_result, listen_future_result_method)(listen_future_result)
        client.async_send_command.side_effect = original_send_command_side_effect
        # Yield to allow the listen task to run
        await asyncio.sleep(0)

    async def listen(driver_ready: asyncio.Event) -> None:
        """Mock listen."""
        driver_ready.set()
        client.async_send_command.side_effect = send_command_side_effect
        await listen_block.wait()
        await listen_result

    client.listen.side_effect = listen
    hass.set_state(core_state)

    entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": True},
    )
    entry.add_to_hass(hass)
    assert client.disconnect.call_count == 0

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert client.disconnect.call_count == 1


@pytest.mark.parametrize(
    ("core_state", "disconnect_call_count"),
    [
        (
            CoreState.running,
            1,
        ),  # the reload will cause a disconnect
        (
            CoreState.stopping,
            0,
        ),  # the home assistant stop event will handle the disconnect
    ],
)
@pytest.mark.parametrize(
    ("listen_future_result_method", "listen_future_result"),
    [
        ("set_exception", BaseZwaveJSServerError("Boom")),
        ("set_exception", Exception("Boom")),
        ("set_result", None),
    ],
)
async def test_listen_done_after_setup(
    hass: HomeAssistant,
    client: MagicMock,
    listen_block: asyncio.Event,
    core_state: CoreState,
    listen_future_result_method: str,
    listen_future_result: Exception | None,
    disconnect_call_count: int,
) -> None:
    """Test listen task finishing after setup."""
    listen_result = asyncio.Future[None]()

    async def listen(driver_ready: asyncio.Event) -> None:
        driver_ready.set()
        await listen_block.wait()
        await listen_result

    client.listen.side_effect = listen

    config_entry = MockConfigEntry(
        domain="zwave_js",
        data={"url": "ws://test.org", "data_collection_opted_in": True},
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.state is CoreState.running
    assert config_entry.state is ConfigEntryState.LOADED
    assert client.disconnect.call_count == 0

    hass.set_state(core_state)
    listen_block.set()
    getattr(listen_result, listen_future_result_method)(listen_future_result)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert client.disconnect.call_count == disconnect_call_count


async def test_listen_ending_before_cancelling_listen(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    listen_block: asyncio.Event,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test listen ending during unloading before cancelling the listen task."""
    config_entry = integration

    # We can't easily simulate the race condition where the listen task ends
    # before getting cancelled by the config entry during unloading.
    # Use mock_state to provoke the correct condition.
    config_entry.mock_state(hass, ConfigEntryState.UNLOAD_IN_PROGRESS, None)
    listen_block.set()
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.UNLOAD_IN_PROGRESS
    assert not any(record.levelno == logging.ERROR for record in caplog.records)


async def test_listen_ending_unrecoverable_config_entry_state(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    listen_block: asyncio.Event,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test listen ending when the config entry has an unrecoverable state."""
    config_entry = integration

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        await hass.config_entries.async_unload(config_entry.entry_id)

    listen_block.set()
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert "Disconnected from server. Cannot recover entry" in caplog.text


@pytest.mark.usefixtures("client")
@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_new_entity_on_value_added(
    hass: HomeAssistant,
    multisensor_6: Node,
    integration: MockConfigEntry,
) -> None:
    """Test we create a new entity if a value is added after the fact."""
    node: Node = multisensor_6

    # Add a value on a random endpoint so we can be sure we should get a new entity
    event = Event(
        type="value added",
        data={
            "source": "node",
            "event": "value added",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 10,
                "property": "Ultraviolet",
                "propertyName": "Ultraviolet",
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Ultraviolet",
                    "ccSpecific": {"sensorType": 27, "scale": 0},
                },
                "value": 0,
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.multisensor_6_ultraviolet_10") is not None


@pytest.mark.usefixtures("integration")
async def test_on_node_added_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state: NodeDataType,
    client: MagicMock,
) -> None:
    """Test we handle a node added event with a ready node."""
    node = Node(client, deepcopy(multisensor_6_state))
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity and device not yet added
    assert not device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )


async def test_on_node_added_preprovisioned(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state,
    client,
    integration,
) -> None:
    """Test node added event with a preprovisioned device."""
    dsk = "test"
    node = Node(client, deepcopy(multisensor_6_state))
    device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"provision_{dsk}")},
    )
    provisioning_entry = ProvisioningEntry.from_dict(
        {
            "dsk": dsk,
            "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
            "device_id": device.id,
        }
    )
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entry",
        side_effect=lambda id: provisioning_entry if id == node.node_id else None,
    ):
        event = {"node": node}
        client.driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        device = device_registry.async_get(device.id)
        assert device
        assert device.identifiers == {
            get_device_id(client.driver, node),
            get_device_id_ext(client.driver, node),
        }
        assert device.sw_version == node.firmware_version
        # There should only be the controller and the preprovisioned device
        assert len(device_registry.devices) == 2


@pytest.mark.usefixtures("integration")
async def test_on_node_added_not_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    zp3111_not_ready_state: NodeDataType,
    client: MagicMock,
) -> None:
    """Test we handle a node added event with a non-ready node."""
    device_id = f"{client.driver.controller.home_id}-{zp3111_not_ready_state['nodeId']}"

    assert len(hass.states.async_all()) == 1
    assert len(device_registry.devices) == 1

    node_state = deepcopy(zp3111_not_ready_state)
    node_state["isSecure"] = False

    event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": {},
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    # no extended device identifier yet
    assert len(device.identifiers) == 1

    entities = er.async_entries_for_device(entity_registry, device.id)
    # the only entities are the node status sensor, and ping button
    assert len(entities) == 2


async def test_existing_node_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    multisensor_6: Node,
    integration: MockConfigEntry,
) -> None:
    """Test we handle a ready node that exists during integration setup."""
    node = multisensor_6
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"
    air_temperature_device_id_ext = (
        f"{air_temperature_device_id}-{node.manufacturer_id}:"
        f"{node.product_type}:{node.product_id}"
    )

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id_ext)}
    )


async def test_existing_node_reinterview(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: Client,
    multisensor_6_state: NodeDataType,
    multisensor_6: Node,
    integration: MockConfigEntry,
) -> None:
    """Test we handle a node re-interview firing a node ready event."""
    node = multisensor_6
    assert client.driver is not None
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"
    air_temperature_device_id_ext = (
        f"{air_temperature_device_id}-{node.manufacturer_id}:"
        f"{node.product_type}:{node.product_id}"
    )

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id_ext)}
    )
    assert device.sw_version == "1.12"

    node_state = deepcopy(multisensor_6_state)
    node_state["firmwareVersion"] = "1.13"
    event = Event(
        type="ready",
        data={
            "source": "node",
            "event": "ready",
            "nodeId": node.node_id,
            "nodeState": node_state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state != STATE_UNAVAILABLE
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id)}
    )
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, air_temperature_device_id_ext)}
    )
    assert device.sw_version == "1.13"


async def test_existing_node_not_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    zp3111_not_ready: Node,
    integration: MockConfigEntry,
) -> None:
    """Test we handle a non-ready node that exists during integration setup."""
    node = zp3111_not_ready
    device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device.name == f"Node {node.node_id}"
    assert not device.manufacturer
    assert not device.model
    assert not device.sw_version

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    # no extended device identifier yet
    assert len(device.identifiers) == 1

    entities = er.async_entries_for_device(entity_registry, device.id)
    # the only entities are the node status sensor, and ping button
    assert len(entities) == 2


async def test_existing_node_not_replaced_when_not_ready(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    zp3111: Node,
    zp3111_not_ready_state: NodeDataType,
    zp3111_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test when a node added event with a non-ready node is received.

    The existing node should not be replaced, and no customization should be lost.
    """
    kitchen_area = area_registry.async_create("Kitchen")

    device_id = f"{client.driver.controller.home_id}-{zp3111.node_id}"
    device_id_ext = (
        f"{device_id}-{zp3111.manufacturer_id}:"
        f"{zp3111.product_type}:{zp3111.product_id}"
    )

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device.name == "4-in-1 Sensor"
    assert not device.name_by_user
    assert device.manufacturer == "Vision Security"
    assert device.model == "ZP3111-5"
    assert device.sw_version == "5.1"
    assert not device.area_id
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, device_id_ext)}
    )

    motion_entity = "binary_sensor.4_in_1_sensor_motion_detection"
    state = hass.states.get(motion_entity)
    assert state
    assert state.name == "4-in-1 Sensor Motion detection"

    device_registry.async_update_device(
        device.id, name_by_user="Custom Device Name", area_id=kitchen_area.id
    )

    custom_device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert custom_device
    assert custom_device.name == "4-in-1 Sensor"
    assert custom_device.name_by_user == "Custom Device Name"
    assert custom_device.manufacturer == "Vision Security"
    assert custom_device.model == "ZP3111-5"
    assert device.sw_version == "5.1"
    assert custom_device.area_id == kitchen_area.id
    assert custom_device == device_registry.async_get_device(
        identifiers={(DOMAIN, device_id_ext)}
    )

    custom_entity = "binary_sensor.custom_motion_sensor"
    entity_registry.async_update_entity(
        motion_entity, new_entity_id=custom_entity, name="Custom Entity Name"
    )
    await hass.async_block_till_done()
    state = hass.states.get(custom_entity)
    assert state
    assert state.name == "Custom Entity Name"
    assert not hass.states.get(motion_entity)

    node_state = deepcopy(zp3111_not_ready_state)
    node_state["isSecure"] = False

    event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": {},
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, device_id_ext)}
    )
    assert device.id == custom_device.id
    assert device.identifiers == custom_device.identifiers
    assert device.name == f"Node {zp3111.node_id}"
    assert device.name_by_user == "Custom Device Name"
    assert not device.manufacturer
    assert not device.model
    assert not device.sw_version
    assert device.area_id == kitchen_area.id

    state = hass.states.get(custom_entity)
    assert state
    assert state.name == "Custom Entity Name"

    event = Event(
        type="ready",
        data={
            "source": "node",
            "event": "ready",
            "nodeId": zp3111_state["nodeId"],
            "nodeState": deepcopy(zp3111_state),
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, device_id_ext)}
    )
    assert device.id == custom_device.id
    assert device.identifiers == custom_device.identifiers
    assert device.name == "4-in-1 Sensor"
    assert device.name_by_user == "Custom Device Name"
    assert device.manufacturer == "Vision Security"
    assert device.model == "ZP3111-5"
    assert device.area_id == kitchen_area.id
    assert device.sw_version == "5.1"

    state = hass.states.get(custom_entity)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.name == "Custom Entity Name"


@pytest.mark.usefixtures("client")
async def test_null_name(
    hass: HomeAssistant,
    null_name_check: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that node without a name gets a generic node name."""
    node = null_name_check
    assert hass.states.get(f"switch.node_{node.node_id}")


@pytest.mark.usefixtures("addon_installed", "addon_info")
async def test_start_addon(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test start the Z-Wave JS add-on during entry setup."""
    device = "/test"
    s0_legacy_key = "s0_legacy"
    s2_access_control_key = "s2_access_control"
    s2_authenticated_key = "s2_authenticated"
    s2_unauthenticated_key = "s2_unauthenticated"
    lr_s2_access_control_key = "lr_s2_access_control"
    lr_s2_authenticated_key = "lr_s2_authenticated"
    addon_options = {
        "device": device,
        "s0_legacy_key": s0_legacy_key,
        "s2_access_control_key": s2_access_control_key,
        "s2_authenticated_key": s2_authenticated_key,
        "s2_unauthenticated_key": s2_unauthenticated_key,
        "lr_s2_access_control_key": lr_s2_access_control_key,
        "lr_s2_authenticated_key": lr_s2_authenticated_key,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "use_addon": True,
            "usb_path": device,
            "s0_legacy_key": s0_legacy_key,
            "s2_access_control_key": s2_access_control_key,
            "s2_authenticated_key": s2_authenticated_key,
            "s2_unauthenticated_key": s2_unauthenticated_key,
            "lr_s2_access_control_key": lr_s2_access_control_key,
            "lr_s2_authenticated_key": lr_s2_authenticated_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 0
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=addon_options)
    )
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_zwave_js")


@pytest.mark.usefixtures("addon_not_installed", "addon_info")
async def test_install_addon(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test install and start the Z-Wave JS add-on during entry setup."""
    device = "/test"
    s0_legacy_key = "s0_legacy"
    s2_access_control_key = "s2_access_control"
    s2_authenticated_key = "s2_authenticated"
    s2_unauthenticated_key = "s2_unauthenticated"
    addon_options = {
        "device": device,
        "s0_legacy_key": s0_legacy_key,
        "s2_access_control_key": s2_access_control_key,
        "s2_authenticated_key": s2_authenticated_key,
        "s2_unauthenticated_key": s2_unauthenticated_key,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "use_addon": True,
            "usb_path": device,
            "s0_legacy_key": s0_legacy_key,
            "s2_access_control_key": s2_access_control_key,
            "s2_authenticated_key": s2_authenticated_key,
            "s2_unauthenticated_key": s2_unauthenticated_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 1
    assert install_addon.call_args == call("core_zwave_js")
    assert set_addon_options.call_count == 1
    assert set_addon_options.call_args == call(
        "core_zwave_js", AddonsOptions(config=addon_options)
    )
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_zwave_js")


@pytest.mark.usefixtures("addon_installed", "addon_info", "set_addon_options")
@pytest.mark.parametrize("addon_info_side_effect", [SupervisorError("Boom")])
async def test_addon_info_failure(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    start_addon: AsyncMock,
) -> None:
    """Test failure to get add-on info for Z-Wave JS add-on during entry setup."""
    device = "/test"
    network_key = "abc123"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"use_addon": True, "usb_path": device, "network_key": network_key},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0


@pytest.mark.usefixtures("addon_running", "addon_info", "client")
@pytest.mark.parametrize(
    (
        "old_device",
        "new_device",
        "old_s0_legacy_key",
        "new_s0_legacy_key",
        "old_s2_access_control_key",
        "new_s2_access_control_key",
        "old_s2_authenticated_key",
        "new_s2_authenticated_key",
        "old_s2_unauthenticated_key",
        "new_s2_unauthenticated_key",
        "old_lr_s2_access_control_key",
        "new_lr_s2_access_control_key",
        "old_lr_s2_authenticated_key",
        "new_lr_s2_authenticated_key",
    ),
    [
        (
            "/old_test",
            "/new_test",
            "old123",
            "new123",
            "old456",
            "new456",
            "old789",
            "new789",
            "old987",
            "new987",
            "old654",
            "new654",
            "old321",
            "new321",
        )
    ],
)
async def test_addon_options_changed(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    addon_options: dict[str, Any],
    start_addon: AsyncMock,
    old_device: str,
    new_device: str,
    old_s0_legacy_key: str,
    new_s0_legacy_key: str,
    old_s2_access_control_key: str,
    new_s2_access_control_key: str,
    old_s2_authenticated_key: str,
    new_s2_authenticated_key: str,
    old_s2_unauthenticated_key: str,
    new_s2_unauthenticated_key: str,
    old_lr_s2_access_control_key: str,
    new_lr_s2_access_control_key: str,
    old_lr_s2_authenticated_key: str,
    new_lr_s2_authenticated_key: str,
) -> None:
    """Test update config entry data on entry setup if add-on options changed."""
    addon_options["device"] = new_device
    addon_options["s0_legacy_key"] = new_s0_legacy_key
    addon_options["s2_access_control_key"] = new_s2_access_control_key
    addon_options["s2_authenticated_key"] = new_s2_authenticated_key
    addon_options["s2_unauthenticated_key"] = new_s2_unauthenticated_key
    addon_options["lr_s2_access_control_key"] = new_lr_s2_access_control_key
    addon_options["lr_s2_authenticated_key"] = new_lr_s2_authenticated_key
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": True,
            "usb_path": old_device,
            "s0_legacy_key": old_s0_legacy_key,
            "s2_access_control_key": old_s2_access_control_key,
            "s2_authenticated_key": old_s2_authenticated_key,
            "s2_unauthenticated_key": old_s2_unauthenticated_key,
            "lr_s2_access_control_key": old_lr_s2_access_control_key,
            "lr_s2_authenticated_key": old_lr_s2_authenticated_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["usb_path"] == new_device
    assert entry.data["s0_legacy_key"] == new_s0_legacy_key
    assert entry.data["s2_access_control_key"] == new_s2_access_control_key
    assert entry.data["s2_authenticated_key"] == new_s2_authenticated_key
    assert entry.data["s2_unauthenticated_key"] == new_s2_unauthenticated_key
    assert entry.data["lr_s2_access_control_key"] == new_lr_s2_access_control_key
    assert entry.data["lr_s2_authenticated_key"] == new_lr_s2_authenticated_key
    assert install_addon.call_count == 0
    assert start_addon.call_count == 0


@pytest.mark.usefixtures("addon_running")
@pytest.mark.parametrize(
    (
        "addon_version",
        "update_available",
        "update_calls",
        "backup_calls",
        "update_addon_side_effect",
        "create_backup_side_effect",
    ),
    [
        ("1.0.0", True, 1, 1, None, None),
        ("1.0.0", False, 0, 0, None, None),
        ("1.0.0", True, 1, 1, SupervisorError("Boom"), None),
        ("1.0.0", True, 0, 1, None, HassioAPIError("Boom")),
    ],
)
async def test_update_addon(
    hass: HomeAssistant,
    client: MagicMock,
    addon_info: AsyncMock,
    create_backup: AsyncMock,
    update_addon: AsyncMock,
    addon_options: dict[str, Any],
    addon_version: str,
    update_available: bool,
    update_calls: int,
    backup_calls: int,
    update_addon_side_effect: Exception | None,
    create_backup_side_effect: Exception | None,
) -> None:
    """Test update the Z-Wave JS add-on during entry setup."""
    device = "/test"
    network_key = "abc123"
    addon_options["device"] = device
    addon_options["network_key"] = network_key
    addon_info.return_value.version = addon_version
    addon_info.return_value.update_available = update_available
    create_backup.side_effect = create_backup_side_effect
    update_addon.side_effect = update_addon_side_effect
    client.connect.side_effect = InvalidServerVersion(
        VersionInfo("a", "b", 1, 1, 1), 1, "Invalid version"
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": True,
            "usb_path": device,
            "network_key": network_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert create_backup.call_count == backup_calls
    assert update_addon.call_count == update_calls


async def test_issue_registry(
    hass: HomeAssistant,
    client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issue registry."""
    device = "/test"
    network_key = "abc123"

    client.connect.side_effect = InvalidServerVersion(
        VersionInfo("a", "b", 1, 1, 1), 1, "Invalid version"
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": False,
            "usb_path": device,
            "network_key": network_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY

    assert issue_registry.async_get_issue(DOMAIN, "invalid_server_version")

    async def connect():
        await asyncio.sleep(0)
        client.connected = True

    client.connect = AsyncMock(side_effect=connect)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert not issue_registry.async_get_issue(DOMAIN, "invalid_server_version")


@pytest.mark.usefixtures("addon_running", "client")
@pytest.mark.parametrize(
    ("stop_addon_side_effect", "entry_state"),
    [
        (None, ConfigEntryState.NOT_LOADED),
        (SupervisorError("Boom"), ConfigEntryState.FAILED_UNLOAD),
    ],
)
async def test_stop_addon(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    stop_addon: AsyncMock,
    stop_addon_side_effect: Exception | None,
    entry_state: ConfigEntryState,
) -> None:
    """Test stop the Z-Wave JS add-on on entry unload if entry is disabled."""
    stop_addon.side_effect = stop_addon_side_effect
    device = "/test"
    network_key = "abc123"
    addon_options["device"] = device
    addon_options["network_key"] = network_key
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={
            "url": "ws://host1:3001",
            "use_addon": True,
            "usb_path": device,
            "network_key": network_key,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    assert entry.state == entry_state
    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")


@pytest.mark.usefixtures("addon_installed")
async def test_remove_entry(
    hass: HomeAssistant,
    stop_addon: AsyncMock,
    create_backup: AsyncMock,
    uninstall_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test remove the config entry."""
    # test successful remove without created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"integration_created_addon": False},
    )
    entry.add_to_hass(hass)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0

    # test successful remove with created add-on
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"integration_created_addon": True},
    )
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_zwave_js_1.0.0", "addons": ["core_zwave_js"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call("core_zwave_js")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on stop failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    stop_addon.side_effect = SupervisorError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")
    assert create_backup.call_count == 0
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to stop the Z-Wave JS add-on" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test create backup failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    create_backup.side_effect = HassioAPIError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_zwave_js_1.0.0", "addons": ["core_zwave_js"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to create a backup of the Z-Wave JS add-on" in caplog.text
    create_backup.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test add-on uninstall failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    uninstall_addon.side_effect = SupervisorError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        hass,
        {"name": "addon_core_zwave_js_1.0.0", "addons": ["core_zwave_js"]},
        partial=True,
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call("core_zwave_js")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the Z-Wave JS add-on" in caplog.text


@pytest.mark.usefixtures("climate_radio_thermostat_ct100_plus", "lock_schlage_be469")
async def test_removed_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test that the device registry gets updated when a device gets removed."""
    driver = client.driver
    assert driver
    # Verify how many nodes are available
    assert len(driver.controller.nodes) == 3

    # Make sure there are the same number of devices
    device_entries = dr.async_entries_for_config_entry(
        device_registry, integration.entry_id
    )
    assert len(device_entries) == 3

    # Remove a node and reload the entry
    old_node = driver.controller.nodes.pop(13)
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Assert that the node was removed from the device registry
    device_entries = dr.async_entries_for_config_entry(
        device_registry, integration.entry_id
    )
    assert len(device_entries) == 2
    assert (
        device_registry.async_get_device(identifiers={get_device_id(driver, old_node)})
        is None
    )


@pytest.mark.usefixtures("client", "eaton_rf9640_dimmer")
async def test_suggested_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that suggested area works."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(EATON_RF9640_ENTITY)
    assert entity_entry
    assert entity_entry.device_id is not None
    device = device_registry.async_get(entity_entry.device_id)
    assert device
    assert device.area_id is not None


async def test_node_removed(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test that device gets removed when node gets removed."""
    node = Node(client, deepcopy(multisensor_6_state))
    device_id = f"{client.driver.controller.home_id}-{node.node_id}"
    event = {
        "source": "controller",
        "event": "node added",
        "node": multisensor_6_state,
        "result": {},
    }

    client.driver.controller.receive_event(Event("node added", event))
    await hass.async_block_till_done()
    old_device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert old_device
    assert old_device.id

    event = {"node": node, "reason": 0}

    client.driver.controller.emit("node removed", event)
    await hass.async_block_till_done()
    # Assert device has been removed
    assert not device_registry.async_get(old_device.id)


async def test_replace_same_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6: Node,
    multisensor_6_state: NodeDataType,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test when a node is replaced with itself that the device remains."""
    node_id = multisensor_6.node_id
    multisensor_6_state = deepcopy(multisensor_6_state)

    device_id = f"{client.driver.controller.home_id}-{node_id}"
    multisensor_6_device_id = (
        f"{device_id}-{multisensor_6.manufacturer_id}:"
        f"{multisensor_6.product_type}:{multisensor_6.product_id}"
    )

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, multisensor_6_device_id)}
    )
    assert device.manufacturer == "AEON Labs"
    assert device.model == "ZW100"
    dev_id = device.id

    assert hass.states.get(AIR_TEMPERATURE_SENSOR)

    # A replace node event has the extra field "reason"
    # to distinguish it from an exclusion
    event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 3,
            "node": multisensor_6_state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    # Device should still be there after the node was removed
    device = device_registry.async_get(dev_id)
    assert device

    # When the node is replaced, a non-ready node added event is emitted
    event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": {
                "nodeId": node_id,
                "index": 0,
                "status": 4,
                "ready": False,
                "isSecure": False,
                "interviewAttempts": 1,
                "endpoints": [{"nodeId": node_id, "index": 0, "deviceClass": None}],
                "values": [],
                "deviceClass": None,
                "commandClasses": [],
                "interviewStage": "None",
                "statistics": {
                    "commandsTX": 0,
                    "commandsRX": 0,
                    "commandsDroppedRX": 0,
                    "commandsDroppedTX": 0,
                    "timeoutResponse": 0,
                },
                "isControllerNode": False,
            },
            "result": {},
        },
    )

    # Device is still not removed
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    device = device_registry.async_get(dev_id)
    assert device

    event = Event(
        type="ready",
        data={
            "source": "node",
            "event": "ready",
            "nodeId": node_id,
            "nodeState": multisensor_6_state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    # Device is the same
    device = device_registry.async_get(dev_id)
    assert device
    assert device == device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, multisensor_6_device_id)}
    )
    assert device.manufacturer == "AEON Labs"
    assert device.model == "ZW100"

    assert hass.states.get(AIR_TEMPERATURE_SENSOR)


async def test_replace_different_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6: Node,
    multisensor_6_state: NodeDataType,
    hank_binary_switch_state: NodeDataType,
    client: MagicMock,
    integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test when a node is replaced with a different node."""
    node_id = multisensor_6.node_id
    state = deepcopy(hank_binary_switch_state)
    state["nodeId"] = node_id

    device_id = f"{client.driver.controller.home_id}-{node_id}"
    multisensor_6_device_id_ext = (
        f"{device_id}-{multisensor_6.manufacturer_id}:"
        f"{multisensor_6.product_type}:{multisensor_6.product_id}"
    )
    hank_device_id_ext = (
        f"{device_id}-{state['manufacturerId']}:"
        f"{state['productType']}:"
        f"{state['productId']}"
    )

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, multisensor_6_device_id_ext)}
    )
    assert device.manufacturer == "AEON Labs"
    assert device.model == "ZW100"
    dev_id = device.id

    assert hass.states.get(AIR_TEMPERATURE_SENSOR)

    # Remove existing node
    event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 3,
            "node": multisensor_6_state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    # Device should still be there after the node was removed
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, multisensor_6_device_id_ext)}
    )
    assert device
    assert len(device.identifiers) == 2

    # When the node is replaced, a non-ready node added event is emitted
    event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": {
                "nodeId": multisensor_6.node_id,
                "index": 0,
                "status": 4,
                "ready": False,
                "isSecure": False,
                "interviewAttempts": 1,
                "endpoints": [
                    {"nodeId": multisensor_6.node_id, "index": 0, "deviceClass": None}
                ],
                "values": [],
                "deviceClass": None,
                "commandClasses": [],
                "interviewStage": "None",
                "statistics": {
                    "commandsTX": 0,
                    "commandsRX": 0,
                    "commandsDroppedRX": 0,
                    "commandsDroppedTX": 0,
                    "timeoutResponse": 0,
                },
                "isControllerNode": False,
            },
            "result": {},
        },
    )

    # Device is still not removed
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    device = device_registry.async_get(dev_id)
    assert device

    event = Event(
        type="ready",
        data={
            "source": "node",
            "event": "ready",
            "nodeId": node_id,
            "nodeState": state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    # node ID based device identifier should be moved from the old multisensor device
    # to the new hank device and both the old and new devices should exist.
    new_device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert new_device
    hank_device = device_registry.async_get_device(
        identifiers={(DOMAIN, hank_device_id_ext)}
    )
    assert hank_device
    assert hank_device == new_device
    assert hank_device.identifiers == {
        (DOMAIN, device_id),
        (DOMAIN, hank_device_id_ext),
    }
    multisensor_6_device = device_registry.async_get_device(
        identifiers={(DOMAIN, multisensor_6_device_id_ext)}
    )
    assert multisensor_6_device
    assert multisensor_6_device != new_device
    assert multisensor_6_device.identifiers == {(DOMAIN, multisensor_6_device_id_ext)}

    assert new_device.manufacturer == "HANK Electronics Ltd."
    assert new_device.model == "HKZW-SO01"

    # We keep the old entities in case there are customizations that a user wants to
    # keep. They can always delete the device and that will remove the entities as well.
    assert hass.states.get(AIR_TEMPERATURE_SENSOR)
    assert hass.states.get("switch.smart_plug_with_two_usb_ports")

    # Try to add back the first node to see if the device IDs are correct

    # Remove existing node
    event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 3,
            "node": state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    # Device should still be there after the node was removed
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, hank_device_id_ext)}
    )
    assert device
    assert len(device.identifiers) == 2

    # When the node is replaced, a non-ready node added event is emitted
    event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": {
                "nodeId": multisensor_6.node_id,
                "index": 0,
                "status": 4,
                "ready": False,
                "isSecure": False,
                "interviewAttempts": 1,
                "endpoints": [
                    {"nodeId": multisensor_6.node_id, "index": 0, "deviceClass": None}
                ],
                "values": [],
                "deviceClass": None,
                "commandClasses": [],
                "interviewStage": "None",
                "statistics": {
                    "commandsTX": 0,
                    "commandsRX": 0,
                    "commandsDroppedRX": 0,
                    "commandsDroppedTX": 0,
                    "timeoutResponse": 0,
                },
                "isControllerNode": False,
            },
            "result": {},
        },
    )

    client.driver.receive_event(event)
    await hass.async_block_till_done()

    # Mark node as ready
    event = Event(
        type="ready",
        data={
            "source": "node",
            "event": "ready",
            "nodeId": node_id,
            "nodeState": multisensor_6_state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "config", {})

    # node ID based device identifier should be moved from the new hank device
    # to the old multisensor device and both the old and new devices should exist.
    old_device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert old_device
    hank_device = device_registry.async_get_device(
        identifiers={(DOMAIN, hank_device_id_ext)}
    )
    assert hank_device
    assert hank_device != old_device
    assert hank_device.identifiers == {(DOMAIN, hank_device_id_ext)}
    multisensor_6_device = device_registry.async_get_device(
        identifiers={(DOMAIN, multisensor_6_device_id_ext)}
    )
    assert multisensor_6_device
    assert multisensor_6_device == old_device
    assert multisensor_6_device.identifiers == {
        (DOMAIN, device_id),
        (DOMAIN, multisensor_6_device_id_ext),
    }


async def test_node_model_change(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    zp3111: Node,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test when a node's model is changed due to an updated device config file.

    The device and entities should not be removed.
    """
    device_id = f"{client.driver.controller.home_id}-{zp3111.node_id}"
    device_id_ext = (
        f"{device_id}-{zp3111.manufacturer_id}:"
        f"{zp3111.product_type}:{zp3111.product_id}"
    )

    # Verify device and entities have default names/ids
    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, device_id_ext)}
    )
    assert device.manufacturer == "Vision Security"
    assert device.model == "ZP3111-5"
    assert device.name == "4-in-1 Sensor"
    assert not device.name_by_user

    dev_id = device.id

    motion_entity = "binary_sensor.4_in_1_sensor_motion_detection"
    state = hass.states.get(motion_entity)
    assert state
    assert state.name == "4-in-1 Sensor Motion detection"

    # Customize device and entity names/ids
    device_registry.async_update_device(device.id, name_by_user="Custom Device Name")
    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device.id == dev_id
    assert device == device_registry.async_get_device(
        identifiers={(DOMAIN, device_id_ext)}
    )
    assert device.manufacturer == "Vision Security"
    assert device.model == "ZP3111-5"
    assert device.name == "4-in-1 Sensor"
    assert device.name_by_user == "Custom Device Name"

    custom_entity = "binary_sensor.custom_motion_sensor"
    entity_registry.async_update_entity(
        motion_entity, new_entity_id=custom_entity, name="Custom Entity Name"
    )
    await hass.async_block_till_done()
    assert not hass.states.get(motion_entity)
    state = hass.states.get(custom_entity)
    assert state
    assert state.name == "Custom Entity Name"

    # Unload the integration
    assert await hass.config_entries.async_unload(integration.entry_id)
    await hass.async_block_till_done()
    assert integration.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)

    # Simulate changes to the node labels
    zp3111.device_config.data["description"] = "New Device Name"
    zp3111.device_config.data["label"] = "New Device Model"
    zp3111.device_config.data["manufacturer"] = "New Device Manufacturer"

    # Reload integration, it will re-add the nodes
    integration.add_to_hass(hass)
    await hass.config_entries.async_setup(integration.entry_id)
    await hass.async_block_till_done()

    # Device name changes, but the customization is the same
    device = device_registry.async_get(dev_id)
    assert device
    assert device.id == dev_id
    assert device.manufacturer == "New Device Manufacturer"
    assert device.model == "New Device Model"
    assert device.name == "New Device Name"
    assert device.name_by_user == "Custom Device Name"

    assert not hass.states.get(motion_entity)
    state = hass.states.get(custom_entity)
    assert state
    assert state.name == "Custom Entity Name"


@pytest.mark.usefixtures("zp3111", "integration")
async def test_disabled_node_status_entity_on_node_replaced(
    hass: HomeAssistant,
    zp3111_state: NodeDataType,
    client: MagicMock,
) -> None:
    """Test when node replacement event is received, node status sensor is removed."""
    node_status_entity = "sensor.4_in_1_sensor_node_status"
    state = hass.states.get(node_status_entity)
    assert state
    assert state.state != STATE_UNAVAILABLE

    event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 3,
            "node": zp3111_state,
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(node_status_entity)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remove_entity_on_value_removed(
    hass: HomeAssistant,
    zp3111: Node,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test that when entity primary values are removed the entity is removed."""
    idle_cover_status_button_entity = (
        "button.4_in_1_sensor_idle_home_security_cover_status"
    )

    state = hass.states.get(idle_cover_status_button_entity)
    assert state
    assert state.state != STATE_UNAVAILABLE

    # check for expected entities
    binary_cover_entity = "binary_sensor.4_in_1_sensor_tampering_product_cover_removed"
    state = hass.states.get(binary_cover_entity)
    assert state
    assert state.state != STATE_UNAVAILABLE

    battery_level_entity = "sensor.4_in_1_sensor_battery_level"
    state = hass.states.get(battery_level_entity)
    assert state
    assert state.state != STATE_UNAVAILABLE

    unavailable_entities = {
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    }

    # This value ID removal does not remove any entity
    event = Event(
        type="value removed",
        data={
            "source": "node",
            "event": "value removed",
            "nodeId": zp3111.node_id,
            "args": {
                "commandClassName": "Wake Up",
                "commandClass": 132,
                "endpoint": 0,
                "property": "wakeUpInterval",
                "prevValue": 3600,
                "propertyName": "wakeUpInterval",
            },
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    assert all(state != STATE_UNAVAILABLE for state in hass.states.async_all())

    # This value ID removal only affects the battery level entity
    event = Event(
        type="value removed",
        data={
            "source": "node",
            "event": "value removed",
            "nodeId": zp3111.node_id,
            "args": {
                "commandClassName": "Battery",
                "commandClass": 128,
                "endpoint": 0,
                "property": "level",
                "prevValue": 100,
                "propertyName": "level",
            },
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(battery_level_entity)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # This value ID removal affects its multiple notification sensors
    event = Event(
        type="value removed",
        data={
            "source": "node",
            "event": "value removed",
            "nodeId": zp3111.node_id,
            "args": {
                "commandClassName": "Notification",
                "commandClass": 113,
                "endpoint": 0,
                "property": "Home Security",
                "propertyKey": "Cover status",
                "prevValue": 0,
                "propertyName": "Home Security",
                "propertyKeyName": "Cover status",
            },
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(binary_cover_entity)
    assert state
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(idle_cover_status_button_entity)
    assert state
    assert state.state == STATE_UNAVAILABLE

    # existing entities and the entities with removed values should be unavailable
    new_unavailable_entities = {
        state.entity_id
        for state in hass.states.async_all()
        if state.state == STATE_UNAVAILABLE
    }
    assert (
        unavailable_entities
        | {
            battery_level_entity,
            binary_cover_entity,
            idle_cover_status_button_entity,
        }
        == new_unavailable_entities
    )


async def test_identify_event(
    hass: HomeAssistant,
    client: MagicMock,
    multisensor_6: Node,
    integration: MockConfigEntry,
) -> None:
    """Test controller identify event."""
    # One config entry scenario
    event = Event(
        type="identify",
        data={
            "source": "controller",
            "event": "identify",
            "nodeId": multisensor_6.node_id,
        },
    )
    dev_id = get_device_id(client.driver, multisensor_6)
    msg_id = f"{DOMAIN}.identify_controller.{dev_id[1]}"

    client.driver.controller.receive_event(event)
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert notifications[msg_id]["message"].startswith("`Multisensor 6`")
    assert "with the home ID" not in notifications[msg_id]["message"]
    async_dismiss(hass, msg_id)

    # Add mock config entry to simulate having multiple entries
    new_entry = MockConfigEntry(domain=DOMAIN)
    new_entry.add_to_hass(hass)

    # Test case where config entry title and home ID don't match
    client.driver.controller.receive_event(event)
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert (
        "network `Mock Title`, with the home ID `3245146787`"
        in notifications[msg_id]["message"]
    )
    async_dismiss(hass, msg_id)

    # Test case where config entry title and home ID do match
    hass.config_entries.async_update_entry(integration, title="3245146787")
    client.driver.controller.receive_event(event)
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert "network with the home ID `3245146787`" in notifications[msg_id]["message"]


async def test_server_logging(
    hass: HomeAssistant, client: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test automatic server logging functionality."""

    def _reset_mocks():
        client.async_send_command.reset_mock()
        client.enable_server_logging.reset_mock()
        client.disable_server_logging.reset_mock()

    # Set server logging to disabled
    client.server_logging_enabled = False

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Setup logger and set log level to debug to trigger event listener
    assert await async_setup_component(hass, "logger", {"logger": {}})
    assert logging.getLogger("zwave_js_server").getEffectiveLevel() == logging.DEBUG
    client.async_send_command.reset_mock()
    async with async_call_logger_set_level(
        "zwave_js_server", "DEBUG", hass=hass, caplog=caplog
    ):
        assert logging.getLogger("zwave_js_server").getEffectiveLevel() == logging.DEBUG

        # Validate that the server logging was enabled
        assert len(client.async_send_command.call_args_list) == 1
        assert client.async_send_command.call_args[0][0] == {
            "command": "driver.update_log_config",
            "config": {"level": "debug"},
        }
        assert client.enable_server_logging.called
        assert not client.disable_server_logging.called

        _reset_mocks()

        # Emulate server by setting log level to debug
        event = Event(
            type="log config updated",
            data={
                "source": "driver",
                "event": "log config updated",
                "config": {
                    "enabled": False,
                    "level": "debug",
                    "logToFile": True,
                    "filename": "test",
                    "forceConsole": True,
                },
            },
        )
        client.driver.receive_event(event)

        # "Enable" server logging and unload the entry
        client.server_logging_enabled = True
        await hass.config_entries.async_unload(entry.entry_id)

        # Validate that the server logging was disabled
        assert len(client.async_send_command.call_args_list) == 1
        assert client.async_send_command.call_args[0][0] == {
            "command": "driver.update_log_config",
            "config": {"level": "info"},
        }
        assert not client.enable_server_logging.called
        assert client.disable_server_logging.called

        _reset_mocks()

        # Validate that the server logging doesn't get enabled because HA thinks it already
        # is enabled
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert len(client.async_send_command.call_args_list) == 2
        assert "driver.update_log_config" not in {
            call[0][0]["command"] for call in client.async_send_command.call_args_list
        }
        assert not client.enable_server_logging.called
        assert not client.disable_server_logging.called

        _reset_mocks()

        # "Disable" server logging and unload the entry
        client.server_logging_enabled = False
        await hass.config_entries.async_unload(entry.entry_id)

        # Validate that the server logging was not disabled because HA thinks it is already
        # is disabled
        assert len(client.async_send_command.call_args_list) == 0
        assert not client.enable_server_logging.called
        assert not client.disable_server_logging.called


async def test_factory_reset_node(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    client: MagicMock,
    multisensor_6: Node,
    multisensor_6_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test when a node is removed because it was reset."""
    # One config entry scenario
    remove_event = Event(
        type="node removed",
        data={
            "source": "controller",
            "event": "node removed",
            "reason": 5,
            "node": deepcopy(multisensor_6_state),
        },
    )
    dev_id = get_device_id(client.driver, multisensor_6)
    msg_id = f"{DOMAIN}.node_reset_and_removed.{dev_id[1]}"

    client.driver.controller.receive_event(remove_event)
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert notifications[msg_id]["message"].startswith("`Multisensor 6`")
    assert "with the home ID" not in notifications[msg_id]["message"]
    async_dismiss(hass, msg_id)
    await hass.async_block_till_done()
    assert not device_registry.async_get_device(identifiers={dev_id})

    # Add mock config entry to simulate having multiple entries
    new_entry = MockConfigEntry(domain=DOMAIN)
    new_entry.add_to_hass(hass)

    # Re-add the node then remove it again
    add_event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": deepcopy(multisensor_6_state),
            "result": {},
        },
    )
    client.driver.controller.receive_event(add_event)
    await hass.async_block_till_done()
    remove_event.data["node"] = deepcopy(multisensor_6_state)
    client.driver.controller.receive_event(remove_event)
    # Test case where config entry title and home ID don't match
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert (
        "network `Mock Title`, with the home ID `3245146787`"
        in notifications[msg_id]["message"]
    )
    async_dismiss(hass, msg_id)

    # Test case where config entry title and home ID do match
    hass.config_entries.async_update_entry(integration, title="3245146787")
    add_event = Event(
        type="node added",
        data={
            "source": "controller",
            "event": "node added",
            "node": deepcopy(multisensor_6_state),
            "result": {},
        },
    )
    client.driver.controller.receive_event(add_event)
    await hass.async_block_till_done()
    remove_event.data["node"] = deepcopy(multisensor_6_state)
    client.driver.controller.receive_event(remove_event)
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert "network with the home ID `3245146787`" in notifications[msg_id]["message"]


async def test_entity_available_when_node_dead(
    hass: HomeAssistant, client, bulb_6_multi_color, integration
) -> None:
    """Test that entities remain available even when the node is dead."""

    node = bulb_6_multi_color
    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)

    assert state
    assert state.state != STATE_UNAVAILABLE

    # Send dead event to the node
    event = Event(
        "dead", data={"source": "node", "event": "dead", "nodeId": node.node_id}
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    # Entity should remain available even though the node is dead
    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)
    assert state
    assert state.state != STATE_UNAVAILABLE

    # Send alive event to bring the node back
    event = Event(
        "alive", data={"source": "node", "event": "alive", "nodeId": node.node_id}
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    # Entity should still be available
    state = hass.states.get(BULB_6_MULTI_COLOR_LIGHT_ENTITY)
    assert state
    assert state.state != STATE_UNAVAILABLE
