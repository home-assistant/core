"""Test the Z-Wave JS update entities."""

import asyncio
from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.node.firmware import NodeFirmwareUpdateStatus

from homeassistant.components.update import (
    ATTR_AUTO_UPDATE,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
)
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)
from tests.typing import WebSocketGenerator

UPDATE_ENTITY = "update.z_wave_thermostat_firmware"
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


async def test_update_entity_states(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
    caplog: pytest.LogCaptureFixture,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test update entity states."""
    ws_client = await hass_ws_client(hass)

    assert hass.states.get(UPDATE_ENTITY).state == STATE_OFF

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF

    await ws_client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": UPDATE_ENTITY,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] is None

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=2))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert not attrs[ATTR_AUTO_UPDATE]
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert not attrs[ATTR_IN_PROGRESS]
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert attrs[ATTR_RELEASE_URL] is None

    await ws_client.send_json(
        {
            "id": 2,
            "type": "update/release_notes",
            "entity_id": UPDATE_ENTITY,
        }
    )
    result = await ws_client.receive_json()
    assert result["result"] == "blah 2"

    # Refresh value should not be supported by this entity
    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: UPDATE_ENTITY,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "There is no value to refresh for this entity" in caplog.text

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=3))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF

    # Assert a node firmware update entity is not created for the controller
    driver = client.driver
    node = driver.controller.nodes[1]
    assert node.is_controller_node
    assert (
        entity_registry.async_get_entity_id(
            DOMAIN,
            "sensor",
            f"{get_valueless_base_unique_id(driver, node)}.firmware_update",
        )
        is None
    )

    client.async_send_command.reset_mock()


async def test_update_entity_install_raises(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test update entity install raises exception."""
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    # Test failed installation by driver
    client.async_send_command.side_effect = FailedZWaveCommand("test", 12, "test")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )


async def test_update_entity_sleep(
    hass: HomeAssistant,
    client,
    zen_31,
    integration,
) -> None:
    """Test update occurs when device is asleep after it wakes up."""
    event = Event(
        "sleep",
        data={"source": "node", "event": "sleep", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    client.async_send_command.reset_mock()

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    # Because node is asleep we shouldn't attempt to check for firmware updates
    assert len(client.async_send_command.call_args_list) == 0

    event = Event(
        "wake up",
        data={"source": "node", "event": "wake up", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    await hass.async_block_till_done()

    # Now that the node is up we can check for updates
    assert len(client.async_send_command.call_args_list) > 0

    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    assert args["nodeId"] == zen_31.node_id


async def test_update_entity_dead(
    hass: HomeAssistant,
    client,
    zen_31,
    integration,
) -> None:
    """Test update occurs when device is dead after it becomes alive."""
    event = Event(
        "dead",
        data={"source": "node", "event": "dead", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    client.async_send_command.reset_mock()

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    # Because node is asleep we shouldn't attempt to check for firmware updates
    assert len(client.async_send_command.call_args_list) == 0

    event = Event(
        "alive",
        data={"source": "node", "event": "alive", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    await hass.async_block_till_done()

    # Now that the node is up we can check for updates
    assert len(client.async_send_command.call_args_list) > 0

    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    assert args["nodeId"] == zen_31.node_id


async def test_update_entity_ha_not_running(
    hass: HomeAssistant,
    client,
    zen_31,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test update occurs only after HA is running."""
    hass.set_state(CoreState.not_running)

    client.async_send_command.return_value = {"updates": []}

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 1

    await hass.async_start()
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 1

    # Update should be delayed by a day because HA is not running
    hass.set_state(CoreState.starting)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 1

    hass.set_state(CoreState.running)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 2
    args = client.async_send_command.call_args_list[1][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    assert args["nodeId"] == zen_31.node_id


async def test_update_entity_update_failure(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test update entity update failed."""
    assert len(client.async_send_command.call_args_list) == 0
    client.async_send_command.side_effect = FailedZWaveCommand("test", 260, "test")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    assert (
        args["nodeId"]
        == climate_radio_thermostat_ct100_plus_different_endpoints.node_id
    )


async def test_update_entity_progress(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test update entity progress."""
    node = climate_radio_thermostat_ct100_plus_different_endpoints
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {
        "result": {"status": 2, "success": False, "reInterview": False}
    }

    # Test successful install call without a version
    install_task = hass.async_create_task(
        hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )
    )

    # Sleep so that task starts
    await asyncio.sleep(0.1)

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is True

    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": node.node_id,
            "progress": {
                "currentFile": 1,
                "totalFiles": 1,
                "sentFragments": 1,
                "totalFragments": 20,
                "progress": 5.0,
            },
        },
    )
    node.receive_event(event)

    # Validate that the progress is updated
    state = hass.states.get(UPDATE_ENTITY)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] == 5

    event = Event(
        type="firmware update finished",
        data={
            "source": "node",
            "event": "firmware update finished",
            "nodeId": node.node_id,
            "result": {
                "status": NodeFirmwareUpdateStatus.OK_NO_RESTART,
                "success": True,
                "reInterview": False,
            },
        },
    )

    node.receive_event(event)
    await hass.async_block_till_done()

    # Validate that progress is reset and entity reflects new version
    state = hass.states.get(UPDATE_ENTITY)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is False
    assert attrs[ATTR_INSTALLED_VERSION] == "11.2.4"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert state.state == STATE_OFF

    await install_task


async def test_update_entity_install_failed(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity install returns error status."""
    node = climate_radio_thermostat_ct100_plus_different_endpoints
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = {
        "result": {"status": 2, "success": False, "reInterview": False}
    }

    # Test install call - we expect it to finish fail
    install_task = hass.async_create_task(
        hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )
    )

    # Sleep so that task starts
    await asyncio.sleep(0.1)

    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": node.node_id,
            "progress": {
                "currentFile": 1,
                "totalFiles": 1,
                "sentFragments": 1,
                "totalFragments": 20,
                "progress": 5.0,
            },
        },
    )
    node.receive_event(event)

    # Validate that the progress is updated
    state = hass.states.get(UPDATE_ENTITY)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] == 5

    event = Event(
        type="firmware update finished",
        data={
            "source": "node",
            "event": "firmware update finished",
            "nodeId": node.node_id,
            "result": {
                "status": NodeFirmwareUpdateStatus.ERROR_TIMEOUT,
                "success": False,
                "reInterview": False,
            },
        },
    )

    node.receive_event(event)
    await hass.async_block_till_done()

    # Validate that progress is reset and entity reflects old version
    state = hass.states.get(UPDATE_ENTITY)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is False
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert state.state == STATE_ON

    # validate that the install task failed
    with pytest.raises(HomeAssistantError):
        await install_task


async def test_update_entity_reload(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
) -> None:
    """Test update entity maintains state after reload."""
    assert hass.states.get(UPDATE_ENTITY).state == STATE_OFF

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=2))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert not attrs[ATTR_AUTO_UPDATE]
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert not attrs[ATTR_IN_PROGRESS]
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"
    assert attrs[ATTR_RELEASE_URL] is None

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_SKIP,
        {
            ATTR_ENTITY_ID: UPDATE_ENTITY,
        },
        blocking=True,
    )

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "11.2.4"

    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    # Trigger another update and make sure the skipped version is still skipped
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=4))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "11.2.4"


async def test_update_entity_delay(
    hass: HomeAssistant,
    client,
    ge_in_wall_dimmer_switch,
    zen_31,
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

    assert len(client.async_send_command.call_args_list) == 2

    await hass.async_start()
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done(wait_background_tasks=True)

    nodes: set[int] = set()

    assert len(client.async_send_command.call_args_list) == 3
    args = client.async_send_command.call_args_list[2][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    nodes.add(args["nodeId"])

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(client.async_send_command.call_args_list) == 4
    args = client.async_send_command.call_args_list[3][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    nodes.add(args["nodeId"])

    assert len(nodes) == 2
    assert nodes == {ge_in_wall_dimmer_switch.node_id, zen_31.node_id}


async def test_update_entity_partial_restore_data(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test update entity with partial restore data resets state."""
    mock_restore_cache(
        hass,
        [
            State(
                UPDATE_ENTITY,
                STATE_OFF,
                {
                    ATTR_INSTALLED_VERSION: "10.7",
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

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_update_entity_partial_restore_data_2(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test second scenario where update entity has partial restore data."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    UPDATE_ENTITY,
                    STATE_ON,
                    {
                        ATTR_INSTALLED_VERSION: "10.7",
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

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] is None


async def test_update_entity_full_restore_data_skipped_version(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test update entity with full restore data (skipped version) restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    UPDATE_ENTITY,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: "10.7",
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

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] == "11.2.4"
    assert state.attributes[ATTR_LATEST_VERSION] == "11.2.4"


async def test_update_entity_full_restore_data_update_available(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test update entity with full restore data (update available) restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    UPDATE_ENTITY,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: "10.7",
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

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.return_value = {
        "result": {"status": 255, "success": True, "reInterview": False}
    }

    # Test successful install call without a version
    install_task = hass.async_create_task(
        hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )
    )

    # Sleep so that task starts
    await asyncio.sleep(0.1)

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    attrs = state.attributes
    assert attrs[ATTR_IN_PROGRESS] is True

    assert len(client.async_send_command.call_args_list) == 2
    assert client.async_send_command.call_args_list[1][0][0] == {
        "command": "controller.firmware_update_ota",
        "nodeId": climate_radio_thermostat_ct100_plus_different_endpoints.node_id,
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


async def test_update_entity_full_restore_data_no_update_available(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test entity with full restore data (no update available) restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    UPDATE_ENTITY,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: "10.7",
                        ATTR_LATEST_VERSION: "10.7",
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

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] == "10.7"


async def test_update_entity_no_latest_version(
    hass: HomeAssistant,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test entity with no `latest_version` attr restores state."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    UPDATE_ENTITY,
                    STATE_OFF,
                    {
                        ATTR_INSTALLED_VERSION: "10.7",
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

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert state.attributes[ATTR_LATEST_VERSION] == "10.7"


async def test_update_entity_unload_asleep_node(
    hass: HomeAssistant, client, wallmote_central_scene, integration
) -> None:
    """Test unloading config entry after attempting an update for an asleep node."""
    assert len(client.async_send_command.call_args_list) == 0

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5, days=1))
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 0
    assert len(wallmote_central_scene._listeners["wake up"]) == 2

    await hass.config_entries.async_unload(integration.entry_id)
    assert len(wallmote_central_scene._listeners["wake up"]) == 0
