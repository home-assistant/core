"""Test ZHA API."""
import pytest
from homeassistant.components.switch import DOMAIN
from homeassistant.components.zha.api import async_load_api, TYPE, ID
from homeassistant.components.zha.core.const import (
    ATTR_CLUSTER_ID,
    ATTR_CLUSTER_TYPE,
    CLUSTER_TYPE_IN,
    ATTR_IEEE,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_QUIRK_APPLIED,
    ATTR_MANUFACTURER,
    ATTR_ENDPOINT_ID,
)
from homeassistant.components.websocket_api import const
from .common import async_init_zigpy_device


@pytest.fixture
async def zha_client(hass, config_entry, zha_gateway, hass_ws_client):
    """Test zha switch platform."""
    from zigpy.zcl.clusters.general import OnOff, Basic

    # load the ZHA API
    async_load_api(hass)

    # create zigpy device
    await async_init_zigpy_device(
        hass, [OnOff.cluster_id, Basic.cluster_id], [], None, zha_gateway
    )

    # load up switch domain
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    await hass.async_block_till_done()

    return await hass_ws_client(hass)


async def test_device_clusters(hass, config_entry, zha_gateway, zha_client):
    """Test getting device cluster info."""
    await zha_client.send_json(
        {ID: 5, TYPE: "zha/devices/clusters", ATTR_IEEE: "00:0d:6f:00:0a:90:69:e7"}
    )

    msg = await zha_client.receive_json()

    assert len(msg["result"]) == 2

    cluster_infos = sorted(msg["result"], key=lambda k: k[ID])

    cluster_info = cluster_infos[0]
    assert cluster_info[TYPE] == CLUSTER_TYPE_IN
    assert cluster_info[ID] == 0
    assert cluster_info[ATTR_NAME] == "Basic"

    cluster_info = cluster_infos[1]
    assert cluster_info[TYPE] == CLUSTER_TYPE_IN
    assert cluster_info[ID] == 6
    assert cluster_info[ATTR_NAME] == "OnOff"


async def test_device_cluster_attributes(hass, config_entry, zha_gateway, zha_client):
    """Test getting device cluster attributes."""
    await zha_client.send_json(
        {
            ID: 5,
            TYPE: "zha/devices/clusters/attributes",
            ATTR_ENDPOINT_ID: 1,
            ATTR_IEEE: "00:0d:6f:00:0a:90:69:e7",
            ATTR_CLUSTER_ID: 6,
            ATTR_CLUSTER_TYPE: CLUSTER_TYPE_IN,
        }
    )

    msg = await zha_client.receive_json()

    attributes = msg["result"]
    assert len(attributes) == 4

    for attribute in attributes:
        assert attribute[ID] is not None
        assert attribute[ATTR_NAME] is not None


async def test_device_cluster_commands(hass, config_entry, zha_gateway, zha_client):
    """Test getting device cluster commands."""
    await zha_client.send_json(
        {
            ID: 5,
            TYPE: "zha/devices/clusters/commands",
            ATTR_ENDPOINT_ID: 1,
            ATTR_IEEE: "00:0d:6f:00:0a:90:69:e7",
            ATTR_CLUSTER_ID: 6,
            ATTR_CLUSTER_TYPE: CLUSTER_TYPE_IN,
        }
    )

    msg = await zha_client.receive_json()

    commands = msg["result"]
    assert len(commands) == 6

    for command in commands:
        assert command[ID] is not None
        assert command[ATTR_NAME] is not None
        assert command[TYPE] is not None


async def test_list_devices(hass, config_entry, zha_gateway, zha_client):
    """Test getting entity cluster commands."""
    await zha_client.send_json({ID: 5, TYPE: "zha/devices"})

    msg = await zha_client.receive_json()

    devices = msg["result"]
    assert len(devices) == 1

    for device in devices:
        assert device[ATTR_IEEE] is not None
        assert device[ATTR_MANUFACTURER] is not None
        assert device[ATTR_MODEL] is not None
        assert device[ATTR_NAME] is not None
        assert device[ATTR_QUIRK_APPLIED] is not None
        assert device["entities"] is not None

        for entity_reference in device["entities"]:
            assert entity_reference[ATTR_NAME] is not None
            assert entity_reference["entity_id"] is not None

        await zha_client.send_json(
            {ID: 6, TYPE: "zha/device", ATTR_IEEE: device[ATTR_IEEE]}
        )
        msg = await zha_client.receive_json()
        device2 = msg["result"]
        assert device == device2


async def test_device_not_found(hass, config_entry, zha_gateway, zha_client):
    """Test not found response from get device API."""
    await zha_client.send_json(
        {ID: 6, TYPE: "zha/device", ATTR_IEEE: "28:6d:97:00:01:04:11:8c"}
    )
    msg = await zha_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND
