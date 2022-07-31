"""The tests for the UniFi Network update platform."""
from copy import deepcopy

from aiounifi.controller import MESSAGE_DEVICE
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING
from yarl import URL

from homeassistant.components.unifi.const import CONF_SITE_ID
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateDeviceClass,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from .test_controller import DESCRIPTION, setup_unifi_integration

DEVICE_1 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "ip": "10.0.1.1",
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "Device 1",
    "next_interval": 20,
    "state": 1,
    "type": "usw",
    "upgradable": True,
    "version": "4.0.42.10433",
    "upgrade_to_firmware": "4.3.17.11279",
}

DEVICE_2 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "ip": "10.0.1.2",
    "mac": "00:00:00:00:01:02",
    "model": "US16P150",
    "name": "Device 2",
    "next_interval": 20,
    "state": 0,
    "type": "usw",
    "version": "4.0.42.10433",
}


async def test_no_entities(hass, aioclient_mock):
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(hass, aioclient_mock)

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 0


async def test_device_updates(
    hass, aioclient_mock, mock_unifi_websocket, mock_device_registry
):
    """Test the update_items function with some devices."""
    device_1 = deepcopy(DEVICE_1)
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[device_1, DEVICE_2],
    )

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 2

    device_1_state = hass.states.get("update.device_1")
    assert device_1_state.state == STATE_ON
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is False
    assert device_1_state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert (
        device_1_state.attributes[ATTR_SUPPORTED_FEATURES]
        == UpdateEntityFeature.PROGRESS | UpdateEntityFeature.INSTALL
    )

    device_2_state = hass.states.get("update.device_2")
    assert device_2_state.state == STATE_OFF
    assert device_2_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_2_state.attributes[ATTR_LATEST_VERSION] == "4.0.42.10433"
    assert device_2_state.attributes[ATTR_IN_PROGRESS] is False
    assert device_2_state.attributes[ATTR_DEVICE_CLASS] == UpdateDeviceClass.FIRMWARE
    assert (
        device_2_state.attributes[ATTR_SUPPORTED_FEATURES]
        == UpdateEntityFeature.PROGRESS | UpdateEntityFeature.INSTALL
    )

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


async def test_not_admin(hass, aioclient_mock):
    """Test that the INSTALL feature is not available on a non-admin account."""
    description = deepcopy(DESCRIPTION)
    description[0]["site_role"] = "not admin"

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        site_description=description,
        devices_response=[DEVICE_1],
    )

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    device_state = hass.states.get("update.device_1")
    assert device_state.state == STATE_ON
    assert (
        device_state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature.PROGRESS
    )


async def test_install(hass, aioclient_mock):
    """Test the device update install call."""
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, devices_response=[DEVICE_1]
    )

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    device_state = hass.states.get("update.device_1")
    assert device_state.state == STATE_ON

    url = f"https://{config_entry.data[CONF_HOST]}:1234/api/s/{config_entry.data[CONF_SITE_ID]}/cmd/devmgr"
    aioclient_mock.clear_requests()
    aioclient_mock.post(url)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.device_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0] == (
        "post",
        URL(url),
        {"cmd": "upgrade", "mac": "00:00:00:00:01:01"},
        {},
    )


async def test_controller_state_change(
    hass, aioclient_mock, mock_unifi_websocket, mock_device_registry
):
    """Verify entities state reflect on controller becoming unavailable."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[DEVICE_1],
    )

    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    assert hass.states.get("update.device_1").state == STATE_ON

    # Controller unavailable
    mock_unifi_websocket(state=STATE_DISCONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get("update.device_1").state == STATE_UNAVAILABLE

    # Controller available
    mock_unifi_websocket(state=STATE_RUNNING)
    await hass.async_block_till_done()

    assert hass.states.get("update.device_1").state == STATE_ON
