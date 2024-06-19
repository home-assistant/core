"""The tests for the UniFi Network update platform."""

from copy import deepcopy

from aiounifi.models.message import MessageKey
import pytest
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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

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


@pytest.mark.parametrize("device_payload", [[DEVICE_1, DEVICE_2]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_updates(hass: HomeAssistant, mock_websocket_message) -> None:
    """Test the update_items function with some devices."""
    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 2

    # Device with new firmware available

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

    # Device without new firmware available

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

    device_1 = deepcopy(DEVICE_1)
    device_1["state"] = 4
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()

    device_1_state = hass.states.get("update.device_1")
    assert device_1_state.state == STATE_ON
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.0.42.10433"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is True

    # Simulate update finished

    device_1["state"] = 0
    device_1["version"] = "4.3.17.11279"
    device_1["upgradable"] = False
    del device_1["upgrade_to_firmware"]
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()

    device_1_state = hass.states.get("update.device_1")
    assert device_1_state.state == STATE_OFF
    assert device_1_state.attributes[ATTR_INSTALLED_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_LATEST_VERSION] == "4.3.17.11279"
    assert device_1_state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
@pytest.mark.parametrize(
    "site_payload",
    [[{"desc": "Site name", "name": "site_id", "role": "not admin", "_id": "1"}]],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_not_admin(hass: HomeAssistant) -> None:
    """Test that the INSTALL feature is not available on a non-admin account."""
    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    device_state = hass.states.get("update.device_1")
    assert device_state.state == STATE_ON
    assert (
        device_state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature.PROGRESS
    )


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
async def test_install(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
) -> None:
    """Test the device update install call."""
    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    device_state = hass.states.get("update.device_1")
    assert device_state.state == STATE_ON

    url = (
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/devmgr"
    )
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


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_hub_state_change(hass: HomeAssistant, mock_websocket_state) -> None:
    """Verify entities state reflect on hub becoming unavailable."""
    assert len(hass.states.async_entity_ids(UPDATE_DOMAIN)) == 1
    assert hass.states.get("update.device_1").state == STATE_ON

    # Controller unavailable
    await mock_websocket_state.disconnect()
    assert hass.states.get("update.device_1").state == STATE_UNAVAILABLE

    # Controller available
    await mock_websocket_state.reconnect()
    assert hass.states.get("update.device_1").state == STATE_ON
