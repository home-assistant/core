"""The tests for the UniFi Network update platform."""

from aiounifi.controller import MESSAGE_DEVICE
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING

from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    UpdateDeviceClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from .test_controller import setup_unifi_integration


async def test_no_entities(hass, aioclient_mock):
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(hass, aioclient_mock)

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 0


async def test_device_updates(
    hass, aioclient_mock, mock_unifi_websocket, mock_device_registry
):
    """Test the update_items function with some devices."""
    device_1 = {
        "board_rev": 3,
        "device_id": "mock-id",
        "has_fan": True,
        "fan_level": 0,
        "ip": "10.0.1.1",
        "last_seen": 1562600145,
        "mac": "00:00:00:00:01:01",
        "model": "US16P150",
        "name": "Device 1",
        "next_interval": 20,
        "overheating": True,
        "state": 1,
        "type": "usw",
        "upgradable": True,
        "version": "4.0.42.10433",
        "upgrade_to_firmware": "4.3.17.11279",
    }
    device_2 = {
        "board_rev": 3,
        "device_id": "mock-id",
        "has_fan": True,
        "ip": "10.0.1.2",
        "mac": "00:00:00:00:01:02",
        "model": "US16P150",
        "name": "Device 2",
        "next_interval": 20,
        "state": 0,
        "type": "usw",
        "version": "4.0.42.10433",
    }
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[device_1, device_2],
    )

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 2

    device_1_state = hass.states.get("update.device_1")
    assert device_1_state.state == STATE_ON
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is False
    assert device_1_state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE

    device_2_state = hass.states.get("update.device_2")
    assert device_2_state.state == STATE_OFF
    assert device_2_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_2_state.attributes[ATTR_LATEST_VERSION] == "4.0.42.10433"
    assert device_2_state.attributes[ATTR_IN_PROGRESS] is False
    assert device_2_state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE

    # Simulate start of update

    device_1["state"] = 4
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_DEVICE},
            "data": [device_1],
        }
    )
    await hass.async_block_till_done()

    device_1_state = hass.states.get("update.device_1")
    assert device_1_state.state == STATE_ON
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is True

    # Simulate update finished

    device_1["state"] = "0"
    device_1["version"] = "4.3.17.11279"
    device_1["upgradable"] = False
    del device_1["upgrade_to_firmware"]
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_DEVICE},
            "data": [device_1],
        }
    )
    await hass.async_block_till_done()

    device_1_state = hass.states.get("update.device_1")
    assert device_1_state.state == STATE_OFF
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is False


async def test_controller_state_change(
    hass, aioclient_mock, mock_unifi_websocket, mock_device_registry
):
    """Verify entities state reflect on controller becoming unavailable."""
    device = {
        "board_rev": 3,
        "device_id": "mock-id",
        "has_fan": True,
        "fan_level": 0,
        "ip": "10.0.1.1",
        "last_seen": 1562600145,
        "mac": "00:00:00:00:01:01",
        "model": "US16P150",
        "name": "Device",
        "next_interval": 20,
        "overheating": True,
        "state": 1,
        "type": "usw",
        "upgradable": True,
        "version": "4.0.42.10433",
        "upgrade_to_firmware": "4.3.17.11279",
    }

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    assert hass.states.get("update.device").state == STATE_ON

    # Controller unavailable
    mock_unifi_websocket(state=STATE_DISCONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get("update.device").state == STATE_UNAVAILABLE

    # Controller available
    mock_unifi_websocket(state=STATE_RUNNING)
    await hass.async_block_till_done()

    assert hass.states.get("update.device").state == STATE_ON
