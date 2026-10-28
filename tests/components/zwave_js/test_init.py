"""Test the Z-Wave JS init module."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import AddonsOptions, PartialBackupOptions
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_call_logger_set_level,
    async_fire_time_changed,
    async_get_persistent_notifications,
)
from pytest_homeassistant.typing import WebSocketGenerator
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

from homeassistant.components.persistent_notification import async_dismiss
from homeassistant.components.zwave_js import DOMAIN
from homeassistant.components.zwave_js.helpers import (
    get_device_id,
    get_device_id_ext,
    get_endpoint_device_id,
)
from homeassistant.components.zwave_js.sensor import ZWaveNumericSensor
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.redact import REDACTED
from homeassistant.setup import async_setup_component

from .common import (
    AIR_TEMPERATURE_SENSOR,
    BULB_6_MULTI_COLOR_LIGHT_ENTITY,
    EATON_RF9640_ENTITY,
    TEST_SENSITIVE_NETWORK_KEY,
)

CONTROLLER_PATCH_PREFIX = "zwave_js_server.model.controller.Controller"


@pytest.fixture(name="connect_timeout")
def connect_timeout_fixture() -> Generator[int]:
    """Mock the connect timeout."""
    with patch("homeassistant.components.zwave_js.CONNECT_TIMEOUT", new=0) as timeout:
        yield timeout


@pytest.mark.parametrize(
    ("unique_id", "data", "expected_unique_id", "expected_data"),
    [
        pytest.param(
            3245146787,
            {"url": "ws://test.org"},
            "3245146787",
            {"url": "ws://test.org"},
            id="int_unique_id",
        ),
        pytest.param(
            "3245146787",
            {"url": "ws://test.org", "network_key": "abc123"},
            "3245146787",
            {"url": "ws://test.org", "s0_legacy_key": "abc123"},
            id="network_key_only",
        ),
        pytest.param(
            "3245146787",
            {
                "url": "ws://test.org",
                "network_key": "abc123",
                "s0_legacy_key": "def456",
            },
            "3245146787",
            {"url": "ws://test.org", "s0_legacy_key": "def456"},
            id="existing_s0_legacy_key_wins",
        ),
    ],
)
@pytest.mark.usefixtures("client")
async def test_migrate_entry(
    hass: HomeAssistant,
    unique_id: int | str,
    data: dict[str, Any],
    expected_unique_id: str,
    expected_data: dict[str, Any],
) -> None:
    """Test migration of a version 1.1 config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, unique_id=unique_id, minor_version=1
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.zwave_js.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.unique_id == expected_unique_id
    assert dict(entry.data) == expected_data


async def test_migrate_entry_from_future_version(hass: HomeAssistant) -> None:
    """Test migration of a config entry from a future version fails."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"url": "ws://test.org"}, unique_id="3245146787", version=2
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


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


async def test_home_assistant_stop_waits_for_neighbors_refresh(
    hass: HomeAssistant,
    integration: MockConfigEntry,
    client: MagicMock,
) -> None:
    """Test stop disconnects only after a neighbors refresh releases the lock.

    The refresh turns the radio back on before releasing, so disconnecting
    earlier could leave the radio off.
    """
    disconnected = asyncio.Event()

    async def mock_disconnect() -> None:
        disconnected.set()

    client.disconnect.side_effect = mock_disconnect

    async with integration.runtime_data.network_neighbors_lock:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        for _ in range(10):
            await asyncio.sleep(0)
        assert not disconnected.is_set()

    await hass.async_block_till_done()
    assert disconnected.is_set()


@pytest.mark.usefixtures("client", "connect_timeout")
async def test_initialized_timeout(hass: HomeAssistant) -> None:
    """Test we handle a timeout during client initialization."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("client")
async def test_enabled_statistics(hass: HomeAssistant) -> None:
    """Test that we enabled statistics if the entry is opted in."""
    entry = MockConfigEntry(
        domain=DOMAIN,
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
        domain=DOMAIN,
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
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://test.org"})
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
        domain=DOMAIN,
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

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://test.org"})
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
        domain=DOMAIN,
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
        domain=DOMAIN,
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
        domain=DOMAIN,
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


async def test_on_node_added_ready(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state: NodeDataType,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test we handle a node added event with a ready node."""
    node = Node(client, deepcopy(multisensor_6_state))
    event = {"node": node}
    air_temperature_device_id = f"{client.driver.controller.home_id}-{node.node_id}"

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert not state  # entity and device not yet added
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id), integration.entry_id
    )

    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state  # entity and device added
    assert state.state != STATE_UNAVAILABLE
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id), integration.entry_id
    )
    assert device

    controller_node = client.driver.controller.own_node
    assert controller_node
    controller_device_id = (
        f"{client.driver.controller.home_id}-{controller_node.node_id}"
    )
    controller_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, controller_device_id), integration.entry_id
    )
    assert controller_device
    assert device.via_device_id == controller_device.id


async def test_check_pre_provisioned_device_update_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state: NodeDataType,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test check pre-provisioned device that should update the device."""
    dsk = "test"
    node = Node(client, deepcopy(multisensor_6_state))
    pre_provisioned_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"provision_{dsk}")},
    )
    provisioning_entry = ProvisioningEntry.from_dict(
        {
            "dsk": dsk,
            "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
            "device_id": pre_provisioned_device.id,
        }
    )
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entry",
        side_effect=lambda id: provisioning_entry if id == node.node_id else None,
    ):
        event = {"node": node}
        client.driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        device = device_registry.async_get(pre_provisioned_device.id)
        assert device
        assert device.identifiers == {
            get_device_id(client.driver, node),
            get_device_id_ext(client.driver, node),
        }
        assert device.sw_version == node.firmware_version
        # There should only be the controller and the pre-provisioned device
        assert len(device_registry.devices) == 2


async def test_check_pre_provisioned_device_remove_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    multisensor_6_state: NodeDataType,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test check pre-provisioned device that should remove the device."""
    dsk = "test"
    driver = client.driver
    node = Node(client, deepcopy(multisensor_6_state))
    pre_provisioned_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={(DOMAIN, f"provision_{dsk}")},
    )
    extended_identifier = get_device_id_ext(driver, node)
    assert extended_identifier
    existing_device = device_registry.async_get_or_create(
        config_entry_id=integration.entry_id,
        identifiers={
            get_device_id(driver, node),
            extended_identifier,
        },
    )
    provisioning_entry = ProvisioningEntry.from_dict(
        {
            "dsk": dsk,
            "securityClasses": [SecurityClass.S2_UNAUTHENTICATED],
            "device_id": pre_provisioned_device.id,
        }
    )
    with patch(
        f"{CONTROLLER_PATCH_PREFIX}.async_get_provisioning_entry",
        side_effect=lambda id: provisioning_entry if id == node.node_id else None,
    ):
        event = {"node": node}
        client.driver.controller.emit("node added", event)
        await hass.async_block_till_done()

        assert not device_registry.async_get(pre_provisioned_device.id)
        assert device_registry.async_get(existing_device.id)

        # There should only be the controller and the existing device
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id_ext), integration.entry_id
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id_ext), integration.entry_id
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, air_temperature_device_id_ext), integration.entry_id
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device.name == f"Node {node.node_id}"
    assert not device.manufacturer
    assert not device.model
    assert not device.sw_version

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device.name == "4-in-1 Sensor"
    assert not device.name_by_user
    assert device.manufacturer == "Vision Security"
    assert device.model == "ZP3111-5"
    assert device.sw_version == "5.1"
    assert not device.area_id
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id_ext), integration.entry_id
    )

    motion_entity = "binary_sensor.4_in_1_sensor_motion_detection"
    state = hass.states.get(motion_entity)
    assert state
    assert state.name == "4-in-1 Sensor Motion detection"

    device_registry.async_update_device(
        device.id, name_by_user="Custom Device Name", area_id=kitchen_area.id
    )

    custom_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert custom_device
    assert custom_device.name == "4-in-1 Sensor"
    assert custom_device.name_by_user == "Custom Device Name"
    assert custom_device.manufacturer == "Vision Security"
    assert custom_device.model == "ZP3111-5"
    assert device.sw_version == "5.1"
    assert custom_device.area_id == kitchen_area.id
    assert custom_device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id_ext), integration.entry_id
    )

    custom_entity = "binary_sensor.custom_motion_sensor"
    entity_registry.async_update_entity(
        motion_entity, new_entity_id=custom_entity, name="Custom Entity Name"
    )
    await hass.async_block_till_done()
    state = hass.states.get(custom_entity)
    assert state
    assert state.name == "Custom Device Name Custom Entity Name"
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id_ext), integration.entry_id
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
    assert state.name == "Custom Device Name Custom Entity Name"

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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id_ext), integration.entry_id
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
    assert state.name == "Custom Device Name Custom Entity Name"


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
@pytest.mark.parametrize(
    "existing_addon_options",
    [
        pytest.param({}, id="unconfigured"),
        pytest.param(
            {
                "device": "/old",
                "log_level": "debug",
                "log_to_file": True,
                "rf_region": "Europe",
            },
            id="user-configured",
        ),
    ],
)
async def test_start_addon(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    addon_options: dict[str, Any],
    existing_addon_options: dict[str, Any],
) -> None:
    """Test entry setup preserves user options when starting the Z-Wave JS add-on."""
    addon_options.update(existing_addon_options)
    device = "/test"
    s0_legacy_key = "s0_legacy"
    s2_access_control_key = "s2_access_control"
    s2_authenticated_key = "s2_authenticated"
    s2_unauthenticated_key = "s2_unauthenticated"
    lr_s2_access_control_key = "lr_s2_access_control"
    lr_s2_authenticated_key = "lr_s2_authenticated"
    expected_options = existing_addon_options | {
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
        "core_zwave_js", AddonsOptions(config=expected_options)
    )
    assert addon_options == expected_options
    assert start_addon.call_count == 1
    assert start_addon.call_args == call("core_zwave_js")


@pytest.mark.usefixtures("addon_installed", "addon_info")
@pytest.mark.parametrize(
    "set_addon_options_side_effect",
    [
        SupervisorError(
            "not a valid value at 'options'. "
            f"Got {{'s0_legacy_key': '{TEST_SENSITIVE_NETWORK_KEY}'}}"
        )
    ],
)
async def test_start_addon_redacts_set_options_error(
    hass: HomeAssistant,
    install_addon: AsyncMock,
    set_addon_options: AsyncMock,
    start_addon: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test startup redacts add-on options backend error details."""
    device = "/test"
    secret = TEST_SENSITIVE_NETWORK_KEY
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Z-Wave JS",
        data={"use_addon": True, "usb_path": device, "network_key": secret},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert install_addon.call_count == 0
    assert set_addon_options.call_count == 1
    assert start_addon.call_count == 0
    assert "Failed to set the Z-Wave JS app options" in caplog.text
    assert "not a valid value at" in caplog.text
    assert REDACTED in caplog.text
    assert secret not in caplog.text


@pytest.mark.usefixtures("addon_info")
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
        ("1.0.0", True, 0, 1, None, SupervisorError("Boom")),
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
    ("stop_addon_side_effect", "entry_state", "entry_reason"),
    [
        (None, ConfigEntryState.NOT_LOADED, None),
        (
            SupervisorError("Boom"),
            ConfigEntryState.FAILED_UNLOAD,
            "Failed to stop the Z-Wave JS app",
        ),
    ],
)
async def test_stop_addon(
    hass: HomeAssistant,
    addon_options: dict[str, Any],
    stop_addon: AsyncMock,
    stop_addon_side_effect: Exception | None,
    entry_state: ConfigEntryState,
    entry_reason: str | None,
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

    assert entry.state is entry_state
    assert entry.reason == entry_reason
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
        PartialBackupOptions(name="addon_core_zwave_js_1.0.0", addons={"core_zwave_js"})
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
    assert "Failed to stop the Z-Wave JS app" in caplog.text
    stop_addon.side_effect = None
    stop_addon.reset_mock()
    create_backup.reset_mock()
    uninstall_addon.reset_mock()

    # test create backup failure
    entry.add_to_hass(hass)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    create_backup.side_effect = SupervisorError()

    await hass.config_entries.async_remove(entry.entry_id)

    assert stop_addon.call_count == 1
    assert stop_addon.call_args == call("core_zwave_js")
    assert create_backup.call_count == 1
    assert create_backup.call_args == call(
        PartialBackupOptions(name="addon_core_zwave_js_1.0.0", addons={"core_zwave_js"})
    )
    assert uninstall_addon.call_count == 0
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to create a backup of the Z-Wave JS app" in caplog.text
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
        PartialBackupOptions(name="addon_core_zwave_js_1.0.0", addons={"core_zwave_js"})
    )
    assert uninstall_addon.call_count == 1
    assert uninstall_addon.call_args == call("core_zwave_js")
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert "Failed to uninstall the Z-Wave JS app" in caplog.text


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
        device_registry.async_get_device_by_identifier(
            get_device_id(driver, old_node), integration.entry_id
        )
        is None
    )


@pytest.mark.usefixtures("client", "eaton_rf9640_dimmer")
async def test_suggested_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that suggested area works."""
    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://test.org"})
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
    old_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert old_device
    assert old_device.id

    node_events = integration.runtime_data.driver_events.controller_events.node_events
    assert node.node_id in node_events.value_updates_disc_info

    event = {"node": node, "reason": 0}

    client.driver.controller.emit("node removed", event)
    await hass.async_block_till_done()
    # Assert device has been removed
    assert not device_registry.async_get(old_device.id)
    # Assert value_updates_disc_info has been cleaned up
    assert node.node_id not in node_events.value_updates_disc_info


async def test_endpoint_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that labeled, colliding endpoints are split into endpoint child devices."""
    node = climate_heatit_z_trm3
    driver = client.driver

    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), integration.entry_id
    )
    assert node_device

    # The air temperature sensors on endpoints 2-4 collide and each endpoint is labeled,
    # so each endpoint gets its own child device named by its endpoint label.
    expected_labels = {2: "Room Sensor", 3: "External Sensor", 4: "Floor Sensor"}
    child_devices: dict[int, dr.ChildDeviceEntry] = {}
    for endpoint, label in expected_labels.items():
        child_device = device_registry.async_get_child_device_by_identifier(
            get_endpoint_device_id(driver, node, node.endpoints[endpoint]),
            integration.entry_id,
        )
        assert child_device
        assert isinstance(child_device, dr.ChildDeviceEntry)
        assert child_device.parent_device_id == node_device.id
        assert child_device.name == label
        child_devices[endpoint] = child_device

    # The child devices appear in the parent's children list.
    children = dr.async_entries_for_parent_device(device_registry, node_device.id)
    assert {child.id for child in children} == {
        child.id for child in child_devices.values()
    }

    # Each air temperature sensor lives on its endpoint child device.
    for endpoint, slug in (
        (2, "room_sensor"),
        (3, "external_sensor"),
        (4, "floor_sensor"),
    ):
        entity = entity_registry.async_get(
            f"sensor.floor_thermostat_{slug}_air_temperature"
        )
        assert entity
        assert entity.device_id == child_devices[endpoint].id

    # The thermostat endpoint is labeled but does not collide, so the climate entity
    # stays on the node device.
    climate = entity_registry.async_get("climate.floor_thermostat")
    assert climate
    assert climate.device_id == node_device.id

    # Removing the node cascades and removes the child devices along with the node device.
    client.driver.controller.emit("node removed", {"node": node, "reason": 0})
    await hass.async_block_till_done()
    assert device_registry.async_get(node_device.id) is None
    for child_device in child_devices.values():
        assert device_registry.async_get(child_device.id) is None


async def test_endpoint_group_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    aeotec_zwa046: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that endpoints in a non-main group share one endpoint child device."""
    node = aeotec_zwa046
    driver = client.driver

    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), integration.entry_id
    )
    assert node_device

    # Each non-main endpoint group (the three clamps) becomes one child device.
    clamp_devices: list[dr.ChildDeviceEntry] = []
    for group_id, label in ((1, "Clamp 1"), (2, "Clamp 2"), (3, "Clamp 3")):
        group = node.endpoint_groups[group_id]
        child_device = device_registry.async_get_child_device_by_identifier(
            get_endpoint_device_id(driver, node, group), integration.entry_id
        )
        assert child_device
        assert isinstance(child_device, dr.ChildDeviceEntry)
        assert child_device.parent_device_id == node_device.id
        assert child_device.name == label
        clamp_devices.append(child_device)

    # Only the three clamp groups produce child devices; the main-device "Total" group
    # stays on the node device.
    children = dr.async_entries_for_parent_device(device_registry, node_device.id)
    assert {child.id for child in children} == {child.id for child in clamp_devices}

    # Clamp 1 holds the entities of both its endpoints (consumption and production).
    clamp_1_entities = er.async_entries_for_device(
        entity_registry, clamp_devices[0].id, include_disabled_entities=True
    )
    clamp_1_endpoints = {entry.unique_id.split("-")[2] for entry in clamp_1_entities}
    assert clamp_1_endpoints == {"1", "2"}

    # The main-device "Total" group endpoints (7-10) stay on the node device. Endpoint 7
    # carries meter (command class 50) values, so its value IDs contain "-50-7-".
    node_entities = er.async_entries_for_device(
        entity_registry, node_device.id, include_disabled_entities=True
    )
    assert any("-50-7-" in entry.unique_id for entry in node_entities)


async def test_endpoint_group_child_device_name_disambiguation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    aeotec_zwa046: Node,
    integration: MockConfigEntry,
) -> None:
    """Test equivalent values on one group child device are disambiguated by label.

    A Clamp group child device covers two endpoints whose "Reset accumulated values"
    buttons would otherwise share a name. They are disambiguated using each endpoint's
    label with the redundant group-label prefix removed (the child device is already
    named by the group label).
    """
    node = aeotec_zwa046
    clamp1_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoint_groups[1]),
        integration.entry_id,
    )
    assert clamp1_device

    reset_names = {
        entry.original_name
        for entry in er.async_entries_for_device(
            entity_registry, clamp1_device.id, include_disabled_entities=True
        )
        if entry.domain == Platform.BUTTON
        and (entry.original_name or "").startswith("Reset accumulated values")
    }
    assert reset_names == {
        "Reset accumulated values Consumption",
        "Reset accumulated values Production",
    }


async def test_endpoint_child_device_pruned_on_reinterview(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    climate_heatit_z_trm3_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test stale endpoint child devices are pruned and surviving entities move to parent.

    When the air temperature sensors on endpoints 3 and 4 disappear on re-interview,
    endpoint 2 no longer collides, so its child device is pruned. The endpoint 2 sensor
    entity must end up on the parent node device while preserving its entity registry
    entry (entity_id, any customizations).
    """
    node = climate_heatit_z_trm3
    driver = client.driver

    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), integration.entry_id
    )
    assert node_device
    room_sensor_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoints[2]), integration.entry_id
    )
    assert room_sensor_device

    # The endpoint 2 sensor lives on its child device before re-interview.
    entity_id = "sensor.floor_thermostat_room_sensor_air_temperature"
    room_sensor = entity_registry.async_get(entity_id)
    assert room_sensor
    assert room_sensor.device_id == room_sensor_device.id

    # Re-interview with the air temperature sensors on endpoints 3 and 4 removed, so
    # endpoint 2 no longer collides.
    new_state = deepcopy(climate_heatit_z_trm3_state)
    # The ready event model requires string name/location (the fixture leaves them null).
    new_state["name"] = new_state.get("name") or ""
    new_state["location"] = new_state.get("location") or ""
    new_state["values"] = [
        value
        for value in new_state["values"]
        if not (value["commandClass"] == 49 and value["endpoint"] in (3, 4))
    ]
    node.receive_event(
        Event(
            "ready",
            {
                "source": "node",
                "event": "ready",
                "nodeId": node.node_id,
                "nodeState": new_state,
            },
        )
    )
    await hass.async_block_till_done()

    # The endpoint 2 child device is pruned since it no longer collides.
    assert device_registry.async_get(room_sensor_device.id) is None
    # Its sensor entity was moved to the parent node device before the child device was
    # removed, preserving the registry entry (same entity_id).
    room_sensor = entity_registry.async_get(entity_id)
    assert room_sensor is not None
    assert room_sensor.device_id == node_device.id
    # The live state is still present — the ready handler re-discovered the value on the
    # parent node device.
    assert hass.states.get(entity_id) is not None


async def test_endpoint_child_device_regrouped_on_reinterview(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    aeotec_zwa046: Node,
    aeotec_zwa046_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test an entity whose endpoint child device changes moves to the new child device.

    When a re-interview changes the "Clamp 1" group's id, its endpoints move to a
    different child device and the old child device is pruned. Across the full
    re-interview sequence (interview started, then ready) the entity ends up on the new
    child device while preserving its entity registry entry (entity_id, customizations):
    the surviving entry is staged on the parent before the old child is removed, so it is
    not deleted with the child device, and rediscovery then moves it to the new child.
    """
    node = aeotec_zwa046
    driver = client.driver

    old_clamp1_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoint_groups[1]),
        integration.entry_id,
    )
    assert old_clamp1_device
    clamp1_entries = er.async_entries_for_device(
        entity_registry, old_clamp1_device.id, include_disabled_entities=True
    )
    assert clamp1_entries
    entity_id = clamp1_entries[0].entity_id
    entity_registry.async_update_entity(entity_id, name="Custom name")

    # The interview-started event removes the live entities first, matching a real
    # re-interview, so rediscovery on ready is not rejected as a duplicate.
    node.receive_event(
        Event(
            "interview started",
            {
                "source": "node",
                "event": "interview started",
                "nodeId": node.node_id,
            },
        )
    )
    await hass.async_block_till_done()

    # Re-interview with the "Clamp 1" group's id changed from 1 to 5, so its endpoints
    # move to a different child device.
    new_state = deepcopy(aeotec_zwa046_state)
    # The ready event model requires string name/location (the fixture leaves them null).
    new_state["name"] = new_state.get("name") or ""
    new_state["location"] = new_state.get("location") or ""
    for group in new_state["endpointGroups"]:
        if group["id"] == 1:
            group["id"] = 5
    node.receive_event(
        Event(
            "ready",
            {
                "source": "node",
                "event": "ready",
                "nodeId": node.node_id,
                "nodeState": new_state,
            },
        )
    )
    await hass.async_block_till_done()

    # The old child device is pruned since its group id no longer exists.
    assert device_registry.async_get(old_clamp1_device.id) is None
    # The entity moved to the new group's child device, keeping the same entity_id and
    # user customization instead of being deleted along with the old child device.
    new_clamp1_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoint_groups[5]),
        integration.entry_id,
    )
    assert new_clamp1_device
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.device_id == new_clamp1_device.id
    assert entry.name == "Custom name"
    assert hass.states.get(entity_id) is not None


async def test_endpoint_child_device_regroup_stages_entity_on_parent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    aeotec_zwa046: Node,
    aeotec_zwa046_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test a surviving entity is staged on the parent before a stale child is removed.

    This isolates the staging safety net: only a ready event is emitted (no interview
    started), so the live entity is never removed and rediscovery cannot immediately
    re-home it to the new child device. The entity registry entry must still be staged
    on the parent node device so it survives the removal of the old child device with its
    entity_id and customizations intact, rather than being deleted alongside it.
    """
    node = aeotec_zwa046
    driver = client.driver

    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), integration.entry_id
    )
    assert node_device
    old_clamp1_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoint_groups[1]),
        integration.entry_id,
    )
    assert old_clamp1_device
    clamp1_entries = er.async_entries_for_device(
        entity_registry, old_clamp1_device.id, include_disabled_entities=True
    )
    assert clamp1_entries
    entity_id = clamp1_entries[0].entity_id
    entity_registry.async_update_entity(entity_id, name="Custom name")

    # Re-interview with the "Clamp 1" group's id changed from 1 to 5, emitting only
    # ready, so the old child device is pruned while the live entity is still registered.
    new_state = deepcopy(aeotec_zwa046_state)
    # The ready event model requires string name/location (the fixture leaves them null).
    new_state["name"] = new_state.get("name") or ""
    new_state["location"] = new_state.get("location") or ""
    for group in new_state["endpointGroups"]:
        if group["id"] == 1:
            group["id"] = 5
    node.receive_event(
        Event(
            "ready",
            {
                "source": "node",
                "event": "ready",
                "nodeId": node.node_id,
                "nodeState": new_state,
            },
        )
    )
    await hass.async_block_till_done()

    # The old child device is pruned since its group id no longer exists.
    assert device_registry.async_get(old_clamp1_device.id) is None
    # The entry was staged on the parent node device, so it survives with the same
    # entity_id and user customization instead of being deleted with the old child.
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.device_id == node_device.id
    assert entry.name == "Custom name"
    assert hass.states.get(entity_id) is not None


async def test_endpoint_child_device_regroup_stages_suffixed_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    aeotec_zw164_siren_state: NodeDataType,
) -> None:
    """Test a suffixed-unique-id entity is staged on the parent during a ready-only regroup.

    Notification binary sensors append a state key to the base value unique id. When a
    labeled endpoint child is pruned in a ready-only regroup, such an entity must still be
    staged on the parent node device (matched by its base value id), not deleted with the
    child device.
    """
    driver = client.driver

    # Label endpoints 3-5 so their colliding "Battery maintenance status" notification
    # sensors split into per-endpoint child devices.
    setup_state = deepcopy(aeotec_zw164_siren_state)
    setup_state["name"] = ""
    setup_state["location"] = ""
    labels = {3: "Doorbell 1", 4: "Doorbell 2", 5: "Doorbell 3"}
    for endpoint in setup_state["endpoints"]:
        if endpoint["index"] in labels:
            endpoint["endpointLabel"] = labels[endpoint["index"]]
    node = Node(client, deepcopy(setup_state))
    driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"url": "ws://test.org"},
        unique_id=str(driver.controller.home_id),
    )
    entry.add_to_hass(hass)
    with patch("homeassistant.components.zwave_js.PLATFORMS", [Platform.BINARY_SENSOR]):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), entry.entry_id
    )
    assert node_device
    doorbell_1_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoints[3]), entry.entry_id
    )
    assert doorbell_1_device
    # The notification binary sensors on endpoint 3 have a state-key suffix
    # ("...Battery maintenance status.10"), so their unique id carries a second ".".
    suffixed_entity_ids = [
        entry_.entity_id
        for entry_ in er.async_entries_for_device(
            entity_registry, doorbell_1_device.id, include_disabled_entities=True
        )
        if entry_.unique_id.count(".") > 1
    ]
    assert suffixed_entity_ids

    # Re-interview (ready only) with endpoints 3-5 moved into a non-main endpoint group,
    # so the per-endpoint children are pruned in favour of a single group child.
    regrouped_state = deepcopy(setup_state)
    regrouped_state["endpointGroups"] = [
        {
            "id": 1,
            "label": "Doorbells",
            "isMainDevice": False,
            "endpointIndices": [3, 4, 5],
        }
    ]
    node.receive_event(
        Event(
            "ready",
            {
                "source": "node",
                "event": "ready",
                "nodeId": node.node_id,
                "nodeState": regrouped_state,
            },
        )
    )
    await hass.async_block_till_done()

    # The suffixed entities were staged on the parent node device, so their registry
    # entries survive the pruning of the per-endpoint child instead of being deleted.
    assert device_registry.async_get(doorbell_1_device.id) is None
    for suffixed_entity_id in suffixed_entity_ids:
        staged_entry = entity_registry.async_get(suffixed_entity_id)
        assert staged_entry is not None
        assert staged_entry.device_id == node_device.id


async def test_endpoint_child_device_late_value(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test a value discovered after node ready lands on its endpoint child device.

    Endpoint 2 already has a child device (its air temperature collides with endpoints 3
    and 4). A value added later on endpoint 2 must be placed on that child device, not on
    the parent node device.
    """
    node = climate_heatit_z_trm3
    child_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    assert child_device

    node.receive_event(
        Event(
            type="value added",
            data={
                "source": "node",
                "event": "value added",
                "nodeId": node.node_id,
                "args": {
                    "commandClassName": "Multilevel Sensor",
                    "commandClass": 49,
                    "endpoint": 2,
                    "property": "Humidity",
                    "propertyName": "Humidity",
                    "metadata": {
                        "type": "number",
                        "readable": True,
                        "writeable": False,
                        "label": "Humidity",
                        "ccSpecific": {"sensorType": 5, "scale": 0},
                        "unit": "%",
                        "stateful": True,
                        "secret": False,
                    },
                    "value": 42,
                },
            },
        )
    )
    await hass.async_block_till_done()

    humidity_entries = [
        entry
        for entry in er.async_entries_for_device(
            entity_registry, child_device.id, include_disabled_entities=True
        )
        if "-49-2-Humidity" in entry.unique_id
    ]
    assert len(humidity_entries) == 1
    assert humidity_entries[0].device_id == child_device.id


async def test_child_device_entity_metadata_rediscovery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that entities on endpoint child devices are re-created after rediscovery.

    A metadata update that triggers rediscovery must remove the entity and re-add it on
    the same endpoint child device, rather than leaving it gone until the next reload.
    """
    node = climate_heatit_z_trm3

    room_sensor_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(client.driver, node, node.endpoints[2]),
        integration.entry_id,
    )
    assert room_sensor_device

    entity_id = "sensor.floor_thermostat_room_sensor_air_temperature"
    sensor_entry = entity_registry.async_get(entity_id)
    assert sensor_entry is not None
    assert sensor_entry.device_id == room_sensor_device.id
    assert hass.states.get(entity_id) is not None

    # Trigger metadata-based rediscovery for the endpoint 2 air temperature sensor.
    # should_rediscover_on_metadata_update normally returns False; patch it to True so
    # the rediscovery path is exercised without a real qualifying metadata change.
    with patch.object(
        ZWaveNumericSensor, "should_rediscover_on_metadata_update", return_value=True
    ):
        node.receive_event(
            Event(
                "metadata updated",
                {
                    "source": "node",
                    "event": "metadata updated",
                    "nodeId": node.node_id,
                    "args": {
                        "commandClassName": "Multilevel Sensor",
                        "commandClass": 49,
                        "endpoint": 2,
                        "property": "Air temperature",
                        "propertyName": "Air temperature",
                        "metadata": {
                            "type": "number",
                            "readable": True,
                            "writeable": False,
                            "label": "Air temperature",
                            "ccSpecific": {"sensorType": 1, "scale": 0},
                            "unit": "°C",
                            "stateful": True,
                            "secret": False,
                        },
                    },
                },
            )
        )
        await hass.async_block_till_done()

    # The entity must be re-created on the same child device (not gone until reload).
    assert hass.states.get(entity_id) is not None
    new_entry = entity_registry.async_get(entity_id)
    assert new_entry is not None
    assert new_entry.device_id == room_sensor_device.id


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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, multisensor_6_device_id), integration.entry_id
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
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, multisensor_6_device_id), integration.entry_id
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

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, multisensor_6_device_id_ext), integration.entry_id
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, multisensor_6_device_id_ext), integration.entry_id
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
    new_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert new_device
    hank_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, hank_device_id_ext), integration.entry_id
    )
    assert hank_device
    assert hank_device == new_device
    assert hank_device.identifiers == {
        (DOMAIN, device_id),
        (DOMAIN, hank_device_id_ext),
    }
    multisensor_6_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, multisensor_6_device_id_ext), integration.entry_id
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, hank_device_id_ext), integration.entry_id
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
    old_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert old_device
    hank_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, hank_device_id_ext), integration.entry_id
    )
    assert hank_device
    assert hank_device != old_device
    assert hank_device.identifiers == {(DOMAIN, hank_device_id_ext)}
    multisensor_6_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, multisensor_6_device_id_ext), integration.entry_id
    )
    assert multisensor_6_device
    assert multisensor_6_device == old_device
    assert multisensor_6_device.identifiers == {
        (DOMAIN, device_id),
        (DOMAIN, multisensor_6_device_id_ext),
    }


async def test_replace_node_with_children(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    climate_heatit_z_trm3_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test replacing a node that has endpoint child devices.

    The old child devices use node-id based identifiers that would collide with the
    replacement node's child devices (reparenting is rejected). They are removed during
    node registration so the replacement's child devices and their entities can be
    created under the new parent device.
    """
    node = climate_heatit_z_trm3
    node_id = node.node_id
    driver = client.driver
    air_temperature_entity_id = "sensor.floor_thermostat_room_sensor_air_temperature"

    old_room_sensor_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoints[2]), integration.entry_id
    )
    assert old_room_sensor_device
    assert entity_registry.async_get(air_temperature_entity_id)

    # The event models require string name/location (the fixture leaves them null).
    removed_state = deepcopy(climate_heatit_z_trm3_state)
    removed_state["name"] = ""
    removed_state["location"] = ""
    # Replacement node: same node id and endpoints, different hardware signature.
    state = deepcopy(removed_state)
    state["manufacturerId"] = climate_heatit_z_trm3_state["manufacturerId"] + 1

    client.driver.receive_event(
        Event(
            type="node removed",
            data={
                "source": "controller",
                "event": "node removed",
                "reason": 3,
                "node": removed_state,
            },
        )
    )
    await hass.async_block_till_done()

    # When the node is replaced, a non-ready node added event is emitted first.
    client.driver.receive_event(
        Event(
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
    )
    await hass.async_block_till_done()

    client.driver.receive_event(
        Event(
            type="ready",
            data={
                "source": "node",
                "event": "ready",
                "nodeId": node_id,
                "nodeState": state,
            },
        )
    )
    await hass.async_block_till_done()

    # The old child's node-based identifier was freed during registration, so the
    # replacement's endpoint 2 child device is created under the new parent device
    # (restored from the removed old child, keeping the same device id) and carries the
    # rediscovered air temperature entity.
    new_node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), integration.entry_id
    )
    assert new_node_device
    new_room_sensor_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoints[2]), integration.entry_id
    )
    assert new_room_sensor_device
    assert new_room_sensor_device.id == old_room_sensor_device.id
    assert new_room_sensor_device.parent_device_id == new_node_device.id
    entry = entity_registry.async_get(air_temperature_entity_id)
    assert entry is not None
    assert entry.device_id == new_room_sensor_device.id


async def test_replace_node_with_children_while_stopped(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_heatit_z_trm3: Node,
    climate_heatit_z_trm3_state: NodeDataType,
    integration: MockConfigEntry,
) -> None:
    """Test a node with children replaced while Home Assistant was stopped.

    No node-removed event fires for an offline replacement, so the stale child devices
    must be reconciled during node registration on the ready event. Otherwise they keep
    their node-based identifiers and the replacement's child devices (and entities) are
    rejected.
    """
    node = climate_heatit_z_trm3
    node_id = node.node_id
    driver = client.driver
    air_temperature_entity_id = "sensor.floor_thermostat_room_sensor_air_temperature"

    old_room_sensor_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoints[2]), integration.entry_id
    )
    assert old_room_sensor_device

    # Different hardware signature, same node id. Only a ready event fires, as on startup
    # after an offline replacement (no node removed / node added events).
    state = deepcopy(climate_heatit_z_trm3_state)
    state["name"] = ""
    state["location"] = ""
    state["manufacturerId"] = climate_heatit_z_trm3_state["manufacturerId"] + 1

    client.driver.receive_event(
        Event(
            type="ready",
            data={
                "source": "node",
                "event": "ready",
                "nodeId": node_id,
                "nodeState": state,
            },
        )
    )
    await hass.async_block_till_done()

    # The stale child was reconciled during registration, so the replacement's endpoint 2
    # child device is created under the new parent device (restored from the removed old
    # child, keeping the same device id) and carries the rediscovered entity.
    new_node_device = device_registry.async_get_device_by_identifier(
        get_device_id(driver, node), integration.entry_id
    )
    assert new_node_device
    new_room_sensor_device = device_registry.async_get_child_device_by_identifier(
        get_endpoint_device_id(driver, node, node.endpoints[2]), integration.entry_id
    )
    assert new_room_sensor_device
    assert new_room_sensor_device.id == old_room_sensor_device.id
    assert new_room_sensor_device.parent_device_id == new_node_device.id
    entry = entity_registry.async_get(air_temperature_entity_id)
    assert entry is not None
    assert entry.device_id == new_room_sensor_device.id


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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id_ext), integration.entry_id
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id), integration.entry_id
    )
    assert device
    assert device.id == dev_id
    assert device == device_registry.async_get_device_by_identifier(
        (DOMAIN, device_id_ext), integration.entry_id
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
    assert state.name == "Custom Device Name Custom Entity Name"

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
    assert state.name == "Custom Device Name Custom Entity Name"


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
    entity_registry: er.EntityRegistry,
    zp3111: Node,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test entity becomes unavailable when primary values removed."""
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

    # Entities should still be in the entity registry (not fully removed)
    assert entity_registry.async_get(battery_level_entity) is not None
    assert entity_registry.async_get(binary_cover_entity) is not None
    assert entity_registry.async_get(idle_cover_status_button_entity) is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_value_removed_and_readded(
    hass: HomeAssistant,
    zp3111: Node,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test entity recovers when primary value is removed and re-added."""
    battery_level_entity = "sensor.4_in_1_sensor_battery_level"

    state = hass.states.get(battery_level_entity)
    assert state
    assert state.state == "0.0"

    # Remove the battery level value
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

    # Re-add the battery level value with a new reading
    event = Event(
        type="value added",
        data={
            "source": "node",
            "event": "value added",
            "nodeId": zp3111.node_id,
            "args": {
                "commandClassName": "Battery",
                "commandClass": 128,
                "endpoint": 0,
                "property": "level",
                "propertyName": "level",
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Battery level",
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                },
                "value": 80,
            },
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(battery_level_entity)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "80.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("platforms", [[Platform.SENSOR]])
async def test_value_never_populated_then_added(
    hass: HomeAssistant,
    zp3111_state: NodeDataType,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test entity updates when value metadata exists but value is None, then added."""
    # Modify the battery level value to have value=None (metadata exists but no data)
    node_state = deepcopy(zp3111_state)
    for value in node_state["values"]:
        if value["commandClass"] == 128 and value["property"] == "level":
            value["value"] = None
            break

    event = Event(
        "node added",
        {
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()

    # The entity should exist but have unknown state (value is None)
    battery_level_entity = "sensor.4_in_1_sensor_battery_level"
    state = hass.states.get(battery_level_entity)
    assert state
    assert state.state == STATE_UNKNOWN

    node = client.driver.controller.nodes[node_state["nodeId"]]

    # Now send "value added" event with actual value
    event = Event(
        type="value added",
        data={
            "source": "node",
            "event": "value added",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Battery",
                "commandClass": 128,
                "endpoint": 0,
                "property": "level",
                "propertyName": "level",
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Battery level",
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                },
                "value": 75,
            },
        },
    )
    client.driver.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(battery_level_entity)
    assert state
    assert state.state == "75.0"


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
        "network `Mock Title`, with the home ID `0xc16d02a3`"
        in notifications[msg_id]["message"]
    )
    async_dismiss(hass, msg_id)

    # Test case where config entry title and home ID do match
    hass.config_entries.async_update_entry(integration, title="0xc16d02a3")
    client.driver.controller.receive_event(event)
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1
    assert list(notifications)[0] == msg_id
    assert "network with the home ID `0xc16d02a3`" in notifications[msg_id]["message"]


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

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://test.org"})
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

        # Validate that the server logging doesn't get enabled
        # because HA thinks it already is enabled
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

        # Validate that the server logging was not disabled
        # because HA thinks it is already disabled
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
    assert not device_registry.async_get_device_by_identifier(
        dev_id, integration.entry_id
    )

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
        "network `Mock Title`, with the home ID `0xc16d02a3`"
        in notifications[msg_id]["message"]
    )
    async_dismiss(hass, msg_id)

    # Test case where config entry title and home ID do match
    hass.config_entries.async_update_entry(integration, title="0xc16d02a3")
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
    assert "network with the home ID `0xc16d02a3`" in notifications[msg_id]["message"]


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


async def test_driver_ready_event(
    hass: HomeAssistant,
    client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test receiving a driver ready event."""
    config_entry = integration
    assert config_entry.state is ConfigEntryState.LOADED

    config_entry_state_changes: list[ConfigEntryState] = []

    def on_config_entry_state_change() -> None:
        """Collect config entry state changes."""
        config_entry_state_changes.append(config_entry.state)

    config_entry.async_on_state_change(on_config_entry_state_change)

    driver_ready = Event(
        type="driver ready",
        data={
            "source": "driver",
            "event": "driver ready",
        },
    )

    client.driver.receive_event(driver_ready)
    await hass.async_block_till_done()

    assert len(config_entry_state_changes) == 4
    assert config_entry_state_changes[0] is ConfigEntryState.UNLOAD_IN_PROGRESS
    assert config_entry_state_changes[1] is ConfigEntryState.NOT_LOADED
    assert config_entry_state_changes[2] is ConfigEntryState.SETUP_IN_PROGRESS
    assert config_entry_state_changes[3] is ConfigEntryState.LOADED
