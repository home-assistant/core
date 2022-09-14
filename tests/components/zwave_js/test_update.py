"""Test the Z-Wave JS update entities."""
import asyncio
from datetime import timedelta

import pytest
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.firmware import FirmwareUpdateStatus

from homeassistant.components.update.const import (
    ATTR_AUTO_UPDATE,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.components.zwave_js.const import DOMAIN, SERVICE_REFRESH_VALUE
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

UPDATE_ENTITY = "update.z_wave_thermostat_firmware"
FIRMWARE_UPDATES = {
    "updates": [
        {
            "version": "10.11.1",
            "changelog": "blah 1",
            "files": [
                {"target": 0, "url": "https://example1.com", "integrity": "sha1"}
            ],
        },
        {
            "version": "11.2.4",
            "changelog": "blah 2",
            "files": [
                {"target": 0, "url": "https://example2.com", "integrity": "sha2"}
            ],
        },
        {
            "version": "11.1.5",
            "changelog": "blah 3",
            "files": [
                {"target": 0, "url": "https://example3.com", "integrity": "sha3"}
            ],
        },
    ]
}


async def test_update_entity_states(
    hass,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    controller_node,
    integration,
    caplog,
    hass_ws_client,
):
    """Test update entity states."""
    ws_client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    assert hass.states.get(UPDATE_ENTITY).state == STATE_OFF

    client.async_send_command.return_value = {"updates": []}

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
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

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=2))
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

    assert "There is no value to refresh for this entity" in caplog.text

    # Assert a node firmware update entity is not created for the controller
    driver = client.driver
    node = driver.controller.nodes[1]
    assert node.is_controller_node
    assert (
        async_get(hass).async_get_entity_id(
            DOMAIN,
            "sensor",
            f"{get_valueless_base_unique_id(driver, node)}.firmware_update",
        )
        is None
    )

    client.async_send_command.reset_mock()


async def test_update_entity_install_raises(
    hass,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
):
    """Test update entity install raises exception."""
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
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
    hass,
    client,
    zen_31,
    integration,
):
    """Test update occurs when device is asleep after it wakes up."""
    event = Event(
        "sleep",
        data={"source": "node", "event": "sleep", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    client.async_send_command.reset_mock()

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
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
    hass,
    client,
    zen_31,
    integration,
):
    """Test update occurs when device is dead after it becomes alive."""
    event = Event(
        "dead",
        data={"source": "node", "event": "dead", "nodeId": zen_31.node_id},
    )
    zen_31.receive_event(event)
    client.async_send_command.reset_mock()

    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
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
    hass,
    client,
    zen_31,
    hass_ws_client,
):
    """Test update occurs after HA starts."""
    await hass.async_stop()

    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(client.async_send_command.call_args_list) == 0

    await hass.async_start()

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args_list[0][0][0]
    assert args["command"] == "controller.get_available_firmware_updates"
    assert args["nodeId"] == zen_31.node_id


async def test_update_entity_update_failure(
    hass,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
):
    """Test update entity update failed."""
    assert len(client.async_send_command.call_args_list) == 0
    client.async_send_command.side_effect = FailedZWaveCommand("test", 260, "test")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
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
    hass,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
):
    """Test update entity progress."""
    node = climate_radio_thermostat_ct100_plus_different_endpoints
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = None

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

    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": node.node_id,
            "sentFragments": 1,
            "totalFragments": 20,
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
            "status": FirmwareUpdateStatus.OK_NO_RESTART,
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
    hass,
    client,
    climate_radio_thermostat_ct100_plus_different_endpoints,
    integration,
    caplog,
):
    """Test update entity install returns error status."""
    node = climate_radio_thermostat_ct100_plus_different_endpoints
    client.async_send_command.return_value = FIRMWARE_UPDATES

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=1))
    await hass.async_block_till_done()

    state = hass.states.get(UPDATE_ENTITY)
    assert state
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == "10.7"
    assert attrs[ATTR_LATEST_VERSION] == "11.2.4"

    client.async_send_command.reset_mock()
    client.async_send_command.return_value = None

    async def call_install():
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: UPDATE_ENTITY,
            },
            blocking=True,
        )

    # Test install call - we expect it to raise
    install_task = hass.async_create_task(call_install())

    # Sleep so that task starts
    await asyncio.sleep(0.1)

    event = Event(
        type="firmware update progress",
        data={
            "source": "node",
            "event": "firmware update progress",
            "nodeId": node.node_id,
            "sentFragments": 1,
            "totalFragments": 20,
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
            "status": FirmwareUpdateStatus.ERROR_TIMEOUT,
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
