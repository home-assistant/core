"""Test the Z-Wave JS update entities."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.driver.firmware import DriverFirmwareUpdateStatus
from zwave_js_server.model.node import Node
from zwave_js_server.model.node.firmware import NodeFirmwareUpdateStatus

from homeassistant.components.update import (
    ATTR_AUTO_UPDATE,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
)
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)
from tests.typing import WebSocketGenerator

NODE_UPDATE_ENTITY = "update.z_wave_thermostat_firmware"
CONTROLLER_UPDATE_ENTITY = "update.z_stick_gen5_usb_controller_firmware"
LATEST_VERSION_FIRMWARE = {
    "version": "11.2.4",
    "changelog": "blah 2",
    "channel": "stable",
    "files": [{"target": 0, "url": "https://example2.com", "integrity": "sha2"}],
    "downgrade": True,
    "normalizedVersion": "11.2.4",
    "device": {
        "manufacturerId": 1,
        "productType": 2,
        "productId": 3,
        "firmwareVersion": "0.4.4",
        "rfRegion": 1,
    },
}
FIRMWARE_UPDATES = {
    "updates": [
        {
            "version": "10.11.1",
            "changelog": "blah 1",
            "channel": "stable",
            "files": [
                {"target": 0, "url": "https://example1.com", "integrity": "sha1"}
            ],
            "downgrade": True,
            "normalizedVersion": "10.11.1",
            "device": {
                "manufacturerId": 1,
                "productType": 2,
                "productId": 3,
                "firmwareVersion": "0.4.4",
                "rfRegion": 1,
            },
        },
        LATEST_VERSION_FIRMWARE,
        {
            "version": "11.1.5",
            "changelog": "blah 3",
            "channel": "stable",
            "files": [
                {"target": 0, "url": "https://example3.com", "integrity": "sha3"}
            ],
            "downgrade": True,
            "normalizedVersion": "11.1.5",
            "device": {
                "manufacturerId": 1,
                "productType": 2,
                "productId": 3,
                "firmwareVersion": "0.4.4",
                "rfRegion": 1,
            },
        },
        # This firmware update should never show because it's in the beta channel
        {
            "version": "999.999.999",
            "changelog": "blah 3",
            "channel": "beta",
            "files": [
                {"target": 0, "url": "https://example3.com", "integrity": "sha3"}
            ],
            "downgrade": True,
            "normalizedVersion": "999.999.999",
            "device": {
                "manufacturerId": 1,
                "productType": 2,
                "productId": 3,
                "firmwareVersion": "0.4.4",
                "rfRegion": 1,
            },
        },
    ]
}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.UPDATE]


@pytest.fixture(name="controller_state", autouse=True)
def controller_state_fixture(
    controller_state: dict[str, Any],
) -> dict[str, Any]:
    """Load the controller state fixture data."""
    controller_state = deepcopy(controller_state)
    # Set the minimum SDK version that supports firmware updates for controllers.
    controller_state["controller"]["sdkVersion"] = "6.50.0"
    return controller_state


@pytest.mark.parametrize(
    ("entity_id", "installed_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2"), (NODE_UPDATE_ENTITY, "10.7")],
)
async def test_update_entity_states(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
) -> None:
    """Test update entity states."""
    ws_client = await hass_ws_client(hass)

    assert client.driver.controller.sdk_version == "6.50.0"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] is None

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=2))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert not attrs[ATTR_AUTO_UPDATE]
    assert attrs[ATTR_INSTALLED_VERSION] == installed_version
    assert attrs[ATTR_IN_PROGRESS] is False
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert attrs[ATTR_RELEASE_URL] is None
    assert attrs[ATTR_UPDATE_PERCENTAGE] is None

    await ws_client.send_json(
        {
            "id": 2,
            "type": "update/release_notes",
            "entity_id": entity_id,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] == "blah 2"

    # Refresh value should not be supported by this entity
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "There is no value to refresh for this entity" in caplog.text

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=3))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "entity_id",
    [CONTROLLER_UPDATE_ENTITY, NODE_UPDATE_ENTITY],
)
async def test_update_entity_install_raises(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
    entity_id: str,
) -> None:
    """Test update entity install raises exception."""
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    # Test failed installation by driver
    client.async_send_command.side_effect = FailedZWaveCommand("test", 12, "test")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )


async def test_update_entity_sleep(
    hass: HomeAssistant,
    client: MagicMock,
    zen_31: Node,
    integration: MockConfigEntry,
) -> None:
    """Test update occurs when device is asleep."""
    event = Event(
        "sleep",
        data={"source": "node", "event": "sleep", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    client.async_send_command.reset_mock()

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    # Two nodes in total, the controller node and the zen_31 node.
    # We should check for updates for both nodes, including the sleeping one
    # since the firmware check no longer requires device communication first.
    assert client.async_send_command.call_count == 2
    # Check calls were made for both nodes
    call_args = [call[0][0] for call in client.async_send_command.call_args_list]
    assert any(args["nodeId"] == 1 for args in call_args)  # Controller node
    assert any(args["nodeId"] == 94 for args in call_args)  # zen_31 node


async def test_update_entity_dead(
    hass: HomeAssistant,
    client: MagicMock,
    zen_31: Node,
    integration: MockConfigEntry,
) -> None:
    """Test update occurs even when device is dead."""
    event = Event(
        "dead",
        data={"source": "node", "event": "dead", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    client.async_send_command.reset_mock()

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    # Two nodes in total, the controller node and the zen_31 node.
    # Checking for firmware updates should proceed even for dead nodes.
    assert client.async_send_command.call_count == 2
    calls = sorted(
        client.async_send_command.call_args_list, key=lambda call: call[0][0]["nodeId"]
    )

    node_ids = (1, 94)
    for node_id, call in zip(node_ids, calls, strict=True):
        args = call[0][0]
        assert args["command"] == "controller.get_available_firmware_updates"
        assert args["nodeId"] == node_id


async def test_update_entity_ha_not_running(
    hass: HomeAssistant,
    client: MagicMock,
    zen_31: Node,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test update occurs only after HA is running."""
    hass.set_state(CoreState.not_running)

    client.async_send_command.return_value = {"updates": []}

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client.async_send_command.reset_mock()
    assert client.async_send_command.call_count == 0

    await hass.async_start()
    await hass.async_block_till_done()

    assert client.async_send_command.call_count == 0

    # Update should be delayed by a day because Home Assistant is not running
    hass.set_state(CoreState.starting)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()

    assert client.async_send_command.call_count == 0

    hass.set_state(CoreState.running)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    # Two nodes in total, the controller node and the zen_31 node.
    assert client.async_send_command.call_count == 2
    calls = sorted(
        client.async_send_command.call_args_list, key=lambda call: call[0][0]["nodeId"]
    )

    node_ids = (1, 94)
    for node_id, call in zip(node_ids, calls, strict=True):
        args = call[0][0]
        assert args["command"] == "controller.get_available_firmware_updates"
        assert args["nodeId"] == node_id


async def test_update_entity_update_failure(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
) -> None:
    """Test update entity update failed."""
    assert client.async_send_command.call_count == 0
    client.async_send_command.side_effect = FailedZWaveCommand("test", 260, "test")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    entity_ids = (CONTROLLER_UPDATE_ENTITY, NODE_UPDATE_ENTITY)
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF

    assert client.async_send_command.call_count == 2
    calls = sorted(
        client.async_send_command.call_args_list, key=lambda call: call[0][0]["nodeId"]
    )

    node_ids = (1, 26)
    for node_id, call in zip(node_ids, calls, strict=True):
        args = call[0][0]
        assert args["command"] == "controller.get_available_firmware_updates"
        assert args["nodeId"] == node_id


@pytest.mark.parametrize(
    (
        "entity_id",
        "installed_version",
        "install_result",
        "progress_event",
        "finished_event",
    ),
    [
        (
            CONTROLLER_UPDATE_ENTITY,
            "1.2",
            {"status": 255, "success": True},
            Event(
                type="firmware update progress",
                data={
                    "source": "driver",
                    "event": "firmware update progress",
                    "progress": {
                        "sentFragments": 1,
                        "totalFragments": 20,
                        "progress": 5.0,
                    },
                },
            ),
            Event(
                type="firmware update finished",
                data={
                    "source": "driver",
                    "event": "firmware update finished",
                    "result": {
                        "status": DriverFirmwareUpdateStatus.OK,
                        "success": True,
                    },
                },
            ),
        ),
        (
            NODE_UPDATE_ENTITY,
            "10.7",
            {"status": 254, "success": True, "reInterview": False},
            Event(
                type="firmware update progress",
                data={
                    "source": "node",
                    "event": "firmware update progress",
                    "nodeId": 26,
                    "progress": {
                        "currentFile": 1,
                        "totalFiles": 1,
                        "sentFragments": 1,
                        "totalFragments": 20,
                        "progress": 5.0,
                    },
                },
            ),
            Event(
                type="firmware update finished",
                data={
                    "source": "node",
                    "event": "firmware update finished",
                    "nodeId": 26,
                    "result": {
                        "status": NodeFirmwareUpdateStatus.OK_NO_RESTART,
                        "success": True,
                        "reInterview": False,
                    },
                },
            ),
        ),
    ],
)
async def test_update_entity_progress(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
    entity_id: str,
    installed_version: str,
    install_result: dict[str, Any],
    progress_event: Event,
    finished_event: Event,
) -> None:
    """Test update entity progress."""
    client.async_send_command.return_value = FIRMWARE_UPDATES
    driver = client.driver

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == installed_version
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"result": install_result}

    # Test successful install call without a version
    install_task = hass.async_create_task(
        hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
    )

    # Sleep so that task starts
    await asyncio.sleep(0.05)

    state = hass.states.get(entity_id)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is True
    assert attrs[ATTR_UPDATE_PERCENTAGE] is None

    driver.receive_event(progress_event)
    await asyncio.sleep(0.05)

    # Validate that the progress is updated
    state = hass.states.get(entity_id)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is True
    assert attrs[ATTR_UPDATE_PERCENTAGE] == 5

    driver.receive_event(finished_event)
    await hass.async_block_till_done()

    # Validate that progress is reset and entity reflects new version
    state = hass.states.get(entity_id)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is False
    assert attrs[ATTR_UPDATE_PERCENTAGE] is None
    assert attrs[ATTR_INSTALLED_VERSION] == "11.2.4"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert state.state == STATE_OFF

    await install_task


@pytest.mark.parametrize(
    (
        "entity_id",
        "installed_version",
        "install_result",
        "progress_event",
        "finished_event",
    ),
    [
        (
            CONTROLLER_UPDATE_ENTITY,
            "1.2",
            {"status": 0, "success": False},
            Event(
                type="firmware update progress",
                data={
                    "source": "driver",
                    "event": "firmware update progress",
                    "progress": {
                        "sentFragments": 1,
                        "totalFragments": 20,
                        "progress": 5.0,
                    },
                },
            ),
            Event(
                type="firmware update finished",
                data={
                    "source": "driver",
                    "event": "firmware update finished",
                    "result": {
                        "status": DriverFirmwareUpdateStatus.ERROR_TIMEOUT,
                        "success": False,
                    },
                },
            ),
        ),
        (
            NODE_UPDATE_ENTITY,
            "10.7",
            {"status": -1, "success": False, "reInterview": False},
            Event(
                type="firmware update progress",
                data={
                    "source": "node",
                    "event": "firmware update progress",
                    "nodeId": 26,
                    "progress": {
                        "currentFile": 1,
                        "totalFiles": 1,
                        "sentFragments": 1,
                        "totalFragments": 20,
                        "progress": 5.0,
                    },
                },
            ),
            Event(
                type="firmware update finished",
                data={
                    "source": "node",
                    "event": "firmware update finished",
                    "nodeId": 26,
                    "result": {
                        "status": NodeFirmwareUpdateStatus.ERROR_TIMEOUT,
                        "success": False,
                        "reInterview": False,
                    },
                },
            ),
        ),
    ],
)
async def test_update_entity_install_failed(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    entity_id: str,
    installed_version: str,
    install_result: dict[str, Any],
    progress_event: Event,
    finished_event: Event,
) -> None:
    """Test update entity install returns error status."""
    driver = client.driver
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == installed_version
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"result": install_result}

    # Test install call - we expect it to finish fail
    install_task = hass.async_create_task(
        hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
    )

    # Sleep so that task starts
    await asyncio.sleep(0.05)

    driver.receive_event(progress_event)
    await asyncio.sleep(0.05)

    # Validate that the progress is updated
    state = hass.states.get(entity_id)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is True
    assert attrs[ATTR_UPDATE_PERCENTAGE] == 5

    driver.receive_event(finished_event)
    await hass.async_block_till_done()

    # Validate that progress is reset and entity reflects old version
    state = hass.states.get(entity_id)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is False
    assert attrs[ATTR_UPDATE_PERCENTAGE] is None
    assert attrs[ATTR_INSTALLED_VERSION] == installed_version
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert state.state == STATE_ON

    # validate that the install task failed
    with pytest.raises(HomeAssistantError):
        await install_task


@pytest.mark.parametrize(
    ("entity_id", "installed_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2"), (NODE_UPDATE_ENTITY, "10.7")],
)
async def test_update_entity_reload(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    integration: MockConfigEntry,
    entity_id: str,
    installed_version: str,
) -> None:
    """Test update entity maintains state after reload."""
    config_entry = integration
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=2))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert not attrs[ATTR_AUTO_UPDATE]
    assert attrs[ATTR_INSTALLED_VERSION] == installed_version
    assert attrs[ATTR_IN_PROGRESS] is False
    assert attrs[ATTR_UPDATE_PERCENTAGE] is None
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert attrs[ATTR_RELEASE_URL] is None

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_SKIP,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "11.2.4"

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Trigger another update and make sure the skipped version is still skipped
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15, days=4))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "11.2.4"


async def test_update_entity_delay(
    hass: HomeAssistant,
    client: MagicMock,
    ge_in_wall_dimmer_switch: Node,
    zen_31: Node,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test update occurs on a delay after HA starts."""
    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"updates": []}
    hass.set_state(CoreState.not_running)

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client.async_send_command.reset_mock()
    assert client.async_send_command.call_count == 0

    await hass.async_start()
    await hass.async_block_till_done()

    assert client.async_send_command.call_count == 0

    update_interval = timedelta(seconds=15)
    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    nodes: set[int] = set()

    assert client.async_send_command.call_count == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    nodes.add(args["nodeId"])

    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_send_command.call_count == 2
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    nodes.add(args["nodeId"])

    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_send_command.call_count == 3
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    nodes.add(args["nodeId"])

    assert len(nodes) == 3
    assert nodes == {1, ge_in_wall_dimmer_switch.node_id, zen_31.node_id}


@pytest.mark.parametrize(
    ("entity_id", "installed_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2"), (NODE_UPDATE_ENTITY, "10.7")],
)
async def test_update_entity_partial_restore_data(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
) -> None:
    """Test update entity with partial restore data resets state."""
    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                STATE_OFF,
                {
                    ATTR_INSTALLED_VERSION: installed_version,
                    ATTR_LATEST_VERSION: "11.2.4",
                    ATTR_SKIPPED_VERSION: "11.2.4",
                },
            )
        ],
    )
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "installed_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2"), (NODE_UPDATE_ENTITY, "10.7")],
)
async def test_update_entity_partial_restore_data_2(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
) -> None:
    """Test second scenario where update entity has partial restore data."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    entity_id,
                    STATE_ON,
                    {
                        ATTR_INSTALLED_VERSION: installed_version,
                        ATTR_LATEST_VERSION: "10.8",
                        ATTR_SKIPPED_VERSION: None,
                    },
                ),
                {"latest_version_firmware": None},
            )
        ],
    )
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None


@pytest.mark.parametrize(
    ("entity_id", "installed_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2"), (NODE_UPDATE_ENTITY, "10.7")],
)
async def test_update_entity_full_restore_data_skipped_version(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
) -> None:
    """Test update entity with full restore data (skipped version) restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    entity_id,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: installed_version,
                        ATTR_LATEST_VERSION: "11.2.4",
                        ATTR_SKIPPED_VERSION: "11.2.4",
                    },
                ),
                {"latest_version_firmware": LATEST_VERSION_FIRMWARE},
            )
        ],
    )
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "11.2.4"
    assert state.attributes[ATTR_LATEST_VERSION] == "11.2.4"


@pytest.mark.parametrize(
    ("entity_id", "installed_version", "install_result", "install_command_params"),
    [
        (
            CONTROLLER_UPDATE_ENTITY,
            "1.2",
            {"status": 255, "success": True},
            {
                "command": "driver.firmware_update_otw",
            },
        ),
        (
            NODE_UPDATE_ENTITY,
            "10.7",
            {"status": 255, "success": True, "reInterview": False},
            {
                "command": "controller.firmware_update_ota",
                "nodeId": 26,
            },
        ),
    ],
)
async def test_update_entity_full_restore_data_update_available(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
    install_result: dict[str, Any],
    install_command_params: dict[str, Any],
) -> None:
    """Test update entity with full restore data (update available) restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    entity_id,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: installed_version,
                        ATTR_LATEST_VERSION: "11.2.4",
                        ATTR_SKIPPED_VERSION: None,
                    },
                ),
                {"latest_version_firmware": LATEST_VERSION_FIRMWARE},
            )
        ],
    )
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {"result": install_result}

    # Test successful install call without a version
    install_task = hass.async_create_task(
        hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )
    )

    # Sleep so that task starts
    await asyncio.sleep(0.05)

    state = hass.states.get(entity_id)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is True
    assert attrs[ATTR_UPDATE_PERCENTAGE] is None

    assert client.async_send_command.call_count == 1
    assert client.async_send_command.call_args[0][0] == {
        **install_command_params,
        "updateInfo": {
            "version": "11.2.4",
            "changelog": "blah 2",
            "channel": "stable",
            "files": [
                {"target": 0, "url": "https://example2.com", "integrity": "sha2"}
            ],
            "downgrade": True,
            "normalizedVersion": "11.2.4",
            "device": {
                "manufacturerId": 1,
                "productType": 2,
                "productId": 3,
                "firmwareVersion": "0.4.4",
                "rfRegion": 1,
            },
        },
    }

    install_task.cancel()


@pytest.mark.parametrize(
    ("entity_id", "installed_version", "latest_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2", "1.2"), (NODE_UPDATE_ENTITY, "10.7", "10.7")],
)
async def test_update_entity_full_restore_data_no_update_available(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
    latest_version: str,
) -> None:
    """Test entity with full restore data (no update available) restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    entity_id,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: installed_version,
                        ATTR_LATEST_VERSION: latest_version,
                        ATTR_SKIPPED_VERSION: None,
                    },
                ),
                {"latest_version_firmware": None},
            )
        ],
    )
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] == latest_version


@pytest.mark.parametrize(
    ("entity_id", "installed_version", "latest_version"),
    [(CONTROLLER_UPDATE_ENTITY, "1.2", "1.2"), (NODE_UPDATE_ENTITY, "10.7", "10.7")],
)
async def test_update_entity_no_latest_version(
    hass: HomeAssistant,
    client: MagicMock,
    climate_radio_thermostat_ct100_plus_different_endpoints: Node,
    hass_ws_client: WebSocketGenerator,
    entity_id: str,
    installed_version: str,
    latest_version: str,
) -> None:
    """Test entity with no `latest_version` attr restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    entity_id,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: installed_version,
                        ATTR_LATEST_VERSION: None,
                        ATTR_SKIPPED_VERSION: None,
                    },
                ),
                {"latest_version_firmware": None},
            )
        ],
    )
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] == latest_version
