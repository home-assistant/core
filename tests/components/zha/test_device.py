"""Test ZHA device API."""
import pytest
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl.clusters.general as general

from homeassistant.components.websocket_api import const
from homeassistant.components.zha.api import ID, TYPE
from homeassistant.components.zha.core.const import (
    ATTR_ENDPOINT_NAMES,
    ATTR_IEEE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_NEIGHBORS,
    ATTR_QUIRK_APPLIED,
)
from homeassistant.helpers.device_registry import async_get_registry
from homeassistant.setup import async_setup_component


@pytest.fixture
async def mock_devices(hass, zigpy_device_mock, zha_device_joined_restored):
    """IAS device fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.Basic.cluster_id],
                "out_clusters": [general.OnOff.cluster_id],
                "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        }
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    zha_device.update_available(True)
    await hass.async_block_till_done()
    return zigpy_device, zha_device


async def test_device_info(hass, hass_ws_client, mock_devices):
    """Test zha device info."""
    ws_client = await hass_ws_client(hass)
    await async_setup_component(hass, "device", {})
    zigpy_device, zha_device = mock_devices

    ieee_address = str(zha_device.ieee)

    ha_device_registry = await async_get_registry(hass)
    reg_device = ha_device_registry.async_get_device({("zha", ieee_address)}, set())

    msg_id = 100
    await ws_client.send_json(
        {ID: msg_id, TYPE: "device/info", "device_id": reg_device.id}
    )
    msg = await ws_client.receive_json()
    config_entry = list(reg_device.config_entries)[0]
    device_info = msg["result"]
    attributes = [
        ATTR_IEEE,
        ATTR_MANUFACTURER,
        ATTR_MODEL,
        ATTR_NAME,
        ATTR_QUIRK_APPLIED,
        "entities",
        ATTR_NEIGHBORS,
        ATTR_ENDPOINT_NAMES,
    ]
    for attribute in attributes:
        assert (
            device_info[config_entry][attribute]
            == zha_device.zha_device_info[attribute]
        )


async def test_device_not_found(hass, hass_ws_client):
    """Test not found response from get device API."""
    ws_client = await hass_ws_client(hass)
    await async_setup_component(hass, "device", {})
    await ws_client.send_json({ID: 6, TYPE: "device/info", "device_id": "12345678"})
    msg = await ws_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND
