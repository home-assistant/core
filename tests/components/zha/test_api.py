"""Test ZHA API."""
from binascii import unhexlify
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl.clusters.general as general

from homeassistant.components.websocket_api import const
from homeassistant.components.zha import DOMAIN
from homeassistant.components.zha.api import (
    ATTR_DURATION,
    ATTR_INSTALL_CODE,
    ATTR_QR_CODE,
    ATTR_SOURCE_IEEE,
    ID,
    SERVICE_PERMIT,
    TYPE,
    async_load_api,
)
from homeassistant.components.zha.core.const import (
    ATTR_CLUSTER_ID,
    ATTR_CLUSTER_TYPE,
    ATTR_ENDPOINT_ID,
    ATTR_ENDPOINT_NAMES,
    ATTR_IEEE,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NEIGHBORS,
    ATTR_QUIRK_APPLIED,
    CLUSTER_TYPE_IN,
    DATA_ZHA,
    DATA_ZHA_GATEWAY,
    GROUP_ID,
    GROUP_IDS,
    GROUP_NAME,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import Context

from .conftest import FIXTURE_GRP_ID, FIXTURE_GRP_NAME

IEEE_SWITCH_DEVICE = "01:2d:6f:00:0a:90:69:e7"
IEEE_GROUPABLE_DEVICE = "01:2d:6f:00:0a:90:69:e8"


@pytest.fixture
async def device_switch(hass, zigpy_device_mock, zha_device_joined):
    """Test zha switch platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [general.OnOff.cluster_id, general.Basic.cluster_id],
                "out_clusters": [],
                "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        },
        ieee=IEEE_SWITCH_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


@pytest.fixture
async def device_groupable(hass, zigpy_device_mock, zha_device_joined):
    """Test zha light platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                "in_clusters": [
                    general.OnOff.cluster_id,
                    general.Basic.cluster_id,
                    general.Groups.cluster_id,
                ],
                "out_clusters": [],
                "device_type": zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


@pytest.fixture
async def zha_client(hass, hass_ws_client, device_switch, device_groupable):
    """Test zha switch platform."""

    # load the ZHA API
    async_load_api(hass)
    return await hass_ws_client(hass)


async def test_device_clusters(hass, zha_client):
    """Test getting device cluster info."""
    await zha_client.send_json(
        {ID: 5, TYPE: "zha/devices/clusters", ATTR_IEEE: IEEE_SWITCH_DEVICE}
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


async def test_device_cluster_attributes(zha_client):
    """Test getting device cluster attributes."""
    await zha_client.send_json(
        {
            ID: 5,
            TYPE: "zha/devices/clusters/attributes",
            ATTR_ENDPOINT_ID: 1,
            ATTR_IEEE: IEEE_SWITCH_DEVICE,
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


async def test_device_cluster_commands(zha_client):
    """Test getting device cluster commands."""
    await zha_client.send_json(
        {
            ID: 5,
            TYPE: "zha/devices/clusters/commands",
            ATTR_ENDPOINT_ID: 1,
            ATTR_IEEE: IEEE_SWITCH_DEVICE,
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


async def test_list_devices(zha_client):
    """Test getting zha devices."""
    await zha_client.send_json({ID: 5, TYPE: "zha/devices"})

    msg = await zha_client.receive_json()

    devices = msg["result"]
    assert len(devices) == 2

    msg_id = 100
    for device in devices:
        msg_id += 1
        assert device[ATTR_IEEE] is not None
        assert device[ATTR_MANUFACTURER] is not None
        assert device[ATTR_MODEL] is not None
        assert device[ATTR_NAME] is not None
        assert device[ATTR_QUIRK_APPLIED] is not None
        assert device["entities"] is not None
        assert device[ATTR_NEIGHBORS] is not None
        assert device[ATTR_ENDPOINT_NAMES] is not None

        for entity_reference in device["entities"]:
            assert entity_reference[ATTR_NAME] is not None
            assert entity_reference["entity_id"] is not None

        await zha_client.send_json(
            {ID: msg_id, TYPE: "zha/device", ATTR_IEEE: device[ATTR_IEEE]}
        )
        msg = await zha_client.receive_json()
        device2 = msg["result"]
        assert device == device2


async def test_device_not_found(zha_client):
    """Test not found response from get device API."""
    await zha_client.send_json(
        {ID: 6, TYPE: "zha/device", ATTR_IEEE: "28:6d:97:00:01:04:11:8c"}
    )
    msg = await zha_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND


async def test_list_groups(zha_client):
    """Test getting zha zigbee groups."""
    await zha_client.send_json({ID: 7, TYPE: "zha/groups"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == const.TYPE_RESULT

    groups = msg["result"]
    assert len(groups) == 1

    for group in groups:
        assert group["group_id"] == FIXTURE_GRP_ID
        assert group["name"] == FIXTURE_GRP_NAME
        assert group["members"] == []


async def test_get_group(zha_client):
    """Test getting a specific zha zigbee group."""
    await zha_client.send_json({ID: 8, TYPE: "zha/group", GROUP_ID: FIXTURE_GRP_ID})

    msg = await zha_client.receive_json()
    assert msg["id"] == 8
    assert msg["type"] == const.TYPE_RESULT

    group = msg["result"]
    assert group is not None
    assert group["group_id"] == FIXTURE_GRP_ID
    assert group["name"] == FIXTURE_GRP_NAME
    assert group["members"] == []


async def test_get_group_not_found(zha_client):
    """Test not found response from get group API."""
    await zha_client.send_json({ID: 9, TYPE: "zha/group", GROUP_ID: 1_234_567})

    msg = await zha_client.receive_json()

    assert msg["id"] == 9
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND


async def test_list_groupable_devices(zha_client, device_groupable):
    """Test getting zha devices that have a group cluster."""

    await zha_client.send_json({ID: 10, TYPE: "zha/devices/groupable"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 10
    assert msg["type"] == const.TYPE_RESULT

    device_endpoints = msg["result"]
    assert len(device_endpoints) == 1

    for endpoint in device_endpoints:
        assert endpoint["device"][ATTR_IEEE] == "01:2d:6f:00:0a:90:69:e8"
        assert endpoint["device"][ATTR_MANUFACTURER] is not None
        assert endpoint["device"][ATTR_MODEL] is not None
        assert endpoint["device"][ATTR_NAME] is not None
        assert endpoint["device"][ATTR_QUIRK_APPLIED] is not None
        assert endpoint["device"]["entities"] is not None
        assert endpoint["endpoint_id"] is not None
        assert endpoint["entities"] is not None

        for entity_reference in endpoint["device"]["entities"]:
            assert entity_reference[ATTR_NAME] is not None
            assert entity_reference["entity_id"] is not None

        for entity_reference in endpoint["entities"]:
            assert entity_reference["original_name"] is not None

    # Make sure there are no groupable devices when the device is unavailable
    # Make device unavailable
    device_groupable.available = False

    await zha_client.send_json({ID: 11, TYPE: "zha/devices/groupable"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 11
    assert msg["type"] == const.TYPE_RESULT

    device_endpoints = msg["result"]
    assert len(device_endpoints) == 0


async def test_add_group(zha_client):
    """Test adding and getting a new zha zigbee group."""
    await zha_client.send_json({ID: 12, TYPE: "zha/group/add", GROUP_NAME: "new_group"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 12
    assert msg["type"] == const.TYPE_RESULT

    added_group = msg["result"]

    assert added_group["name"] == "new_group"
    assert added_group["members"] == []

    await zha_client.send_json({ID: 13, TYPE: "zha/groups"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 13
    assert msg["type"] == const.TYPE_RESULT

    groups = msg["result"]
    assert len(groups) == 2

    for group in groups:
        assert group["name"] == FIXTURE_GRP_NAME or group["name"] == "new_group"


async def test_remove_group(zha_client):
    """Test removing a new zha zigbee group."""

    await zha_client.send_json({ID: 14, TYPE: "zha/groups"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT

    groups = msg["result"]
    assert len(groups) == 1

    await zha_client.send_json(
        {ID: 15, TYPE: "zha/group/remove", GROUP_IDS: [FIXTURE_GRP_ID]}
    )

    msg = await zha_client.receive_json()
    assert msg["id"] == 15
    assert msg["type"] == const.TYPE_RESULT

    groups_remaining = msg["result"]
    assert len(groups_remaining) == 0

    await zha_client.send_json({ID: 16, TYPE: "zha/groups"})

    msg = await zha_client.receive_json()
    assert msg["id"] == 16
    assert msg["type"] == const.TYPE_RESULT

    groups = msg["result"]
    assert len(groups) == 0


@pytest.fixture
async def app_controller(hass, setup_zha):
    """Fixture for zigpy Application Controller."""
    await setup_zha()
    controller = hass.data[DATA_ZHA][DATA_ZHA_GATEWAY].application_controller
    p1 = patch.object(controller, "permit")
    p2 = patch.object(controller, "permit_with_key", new=AsyncMock())
    with p1, p2:
        yield controller


@pytest.mark.parametrize(
    "params, duration, node",
    (
        ({}, 60, None),
        ({ATTR_DURATION: 30}, 30, None),
        (
            {ATTR_DURATION: 33, ATTR_IEEE: "aa:bb:cc:dd:aa:bb:cc:dd"},
            33,
            zigpy.types.EUI64.convert("aa:bb:cc:dd:aa:bb:cc:dd"),
        ),
        (
            {ATTR_IEEE: "aa:bb:cc:dd:aa:bb:cc:d1"},
            60,
            zigpy.types.EUI64.convert("aa:bb:cc:dd:aa:bb:cc:d1"),
        ),
    ),
)
async def test_permit_ha12(
    hass, app_controller, hass_admin_user, params, duration, node
):
    """Test permit service."""

    await hass.services.async_call(
        DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
    )
    assert app_controller.permit.await_count == 1
    assert app_controller.permit.await_args[1]["time_s"] == duration
    assert app_controller.permit.await_args[1]["node"] == node
    assert app_controller.permit_with_key.call_count == 0


IC_TEST_PARAMS = (
    (
        {
            ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
            ATTR_INSTALL_CODE: "5279-7BF4-A508-4DAA-8E17-12B6-1741-CA02-4051",
        },
        zigpy.types.EUI64.convert(IEEE_SWITCH_DEVICE),
        unhexlify("52797BF4A5084DAA8E1712B61741CA024051"),
    ),
    (
        {
            ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
            ATTR_INSTALL_CODE: "52797BF4A5084DAA8E1712B61741CA024051",
        },
        zigpy.types.EUI64.convert(IEEE_SWITCH_DEVICE),
        unhexlify("52797BF4A5084DAA8E1712B61741CA024051"),
    ),
)


@pytest.mark.parametrize("params, src_ieee, code", IC_TEST_PARAMS)
async def test_permit_with_install_code(
    hass, app_controller, hass_admin_user, params, src_ieee, code
):
    """Test permit service with install code."""

    await hass.services.async_call(
        DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
    )
    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_key.call_count == 1
    assert app_controller.permit_with_key.await_args[1]["time_s"] == 60
    assert app_controller.permit_with_key.await_args[1]["node"] == src_ieee
    assert app_controller.permit_with_key.await_args[1]["code"] == code


IC_FAIL_PARAMS = (
    {
        # wrong install code
        ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
        ATTR_INSTALL_CODE: "5279-7BF4-A508-4DAA-8E17-12B6-1741-CA02-4052",
    },
    # incorrect service params
    {ATTR_INSTALL_CODE: "5279-7BF4-A508-4DAA-8E17-12B6-1741-CA02-4051"},
    {ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE},
    {
        # incorrect service params
        ATTR_INSTALL_CODE: "5279-7BF4-A508-4DAA-8E17-12B6-1741-CA02-4051",
        ATTR_QR_CODE: "Z:000D6FFFFED4163B$I:52797BF4A5084DAA8E1712B61741CA024051",
    },
    {
        # incorrect service params
        ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
        ATTR_QR_CODE: "Z:000D6FFFFED4163B$I:52797BF4A5084DAA8E1712B61741CA024051",
    },
    {
        # good regex match, but bad code
        ATTR_QR_CODE: "Z:000D6FFFFED4163B$I:52797BF4A5084DAA8E1712B61741CA024052"
    },
    {
        # good aqara regex match, but bad code
        ATTR_QR_CODE: (
            "G$M:751$S:357S00001579$D:000000000F350FFD%Z$A:04CF8CDF"
            "3C3C3C3C$I:52797BF4A5084DAA8E1712B61741CA024052"
        )
    },
    # good consciot regex match, but bad code
    {ATTR_QR_CODE: "000D6FFFFED4163B|52797BF4A5084DAA8E1712B61741CA024052"},
)


@pytest.mark.parametrize("params", IC_FAIL_PARAMS)
async def test_permit_with_install_code_fail(
    hass, app_controller, hass_admin_user, params
):
    """Test permit service with install code."""

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
        )
    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_key.call_count == 0


IC_QR_CODE_TEST_PARAMS = (
    (
        {ATTR_QR_CODE: "000D6FFFFED4163B|52797BF4A5084DAA8E1712B61741CA024051"},
        zigpy.types.EUI64.convert("00:0D:6F:FF:FE:D4:16:3B"),
        unhexlify("52797BF4A5084DAA8E1712B61741CA024051"),
    ),
    (
        {ATTR_QR_CODE: "Z:000D6FFFFED4163B$I:52797BF4A5084DAA8E1712B61741CA024051"},
        zigpy.types.EUI64.convert("00:0D:6F:FF:FE:D4:16:3B"),
        unhexlify("52797BF4A5084DAA8E1712B61741CA024051"),
    ),
    (
        {
            ATTR_QR_CODE: (
                "G$M:751$S:357S00001579$D:000000000F350FFD%Z$A:04CF8CDF"
                "3C3C3C3C$I:52797BF4A5084DAA8E1712B61741CA024051"
            )
        },
        zigpy.types.EUI64.convert("04:CF:8C:DF:3C:3C:3C:3C"),
        unhexlify("52797BF4A5084DAA8E1712B61741CA024051"),
    ),
)


@pytest.mark.parametrize("params, src_ieee, code", IC_QR_CODE_TEST_PARAMS)
async def test_permit_with_qr_code(
    hass, app_controller, hass_admin_user, params, src_ieee, code
):
    """Test permit service with install code from qr code."""

    await hass.services.async_call(
        DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
    )
    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_key.call_count == 1
    assert app_controller.permit_with_key.await_args[1]["time_s"] == 60
    assert app_controller.permit_with_key.await_args[1]["node"] == src_ieee
    assert app_controller.permit_with_key.await_args[1]["code"] == code


@pytest.mark.parametrize("params, src_ieee, code", IC_QR_CODE_TEST_PARAMS)
async def test_ws_permit_with_qr_code(
    app_controller, zha_client, params, src_ieee, code
):
    """Test permit service with install code from qr code."""

    await zha_client.send_json(
        {ID: 14, TYPE: f"{DOMAIN}/devices/{SERVICE_PERMIT}", **params}
    )

    msg = await zha_client.receive_json()
    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_key.call_count == 1
    assert app_controller.permit_with_key.await_args[1]["time_s"] == 60
    assert app_controller.permit_with_key.await_args[1]["node"] == src_ieee
    assert app_controller.permit_with_key.await_args[1]["code"] == code


@pytest.mark.parametrize("params", IC_FAIL_PARAMS)
async def test_ws_permit_with_install_code_fail(app_controller, zha_client, params):
    """Test permit ws service with install code."""

    await zha_client.send_json(
        {ID: 14, TYPE: f"{DOMAIN}/devices/{SERVICE_PERMIT}", **params}
    )

    msg = await zha_client.receive_json()
    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"] is False

    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_key.call_count == 0


@pytest.mark.parametrize(
    "params, duration, node",
    (
        ({}, 60, None),
        ({ATTR_DURATION: 30}, 30, None),
        (
            {ATTR_DURATION: 33, ATTR_IEEE: "aa:bb:cc:dd:aa:bb:cc:dd"},
            33,
            zigpy.types.EUI64.convert("aa:bb:cc:dd:aa:bb:cc:dd"),
        ),
        (
            {ATTR_IEEE: "aa:bb:cc:dd:aa:bb:cc:d1"},
            60,
            zigpy.types.EUI64.convert("aa:bb:cc:dd:aa:bb:cc:d1"),
        ),
    ),
)
async def test_ws_permit_ha12(app_controller, zha_client, params, duration, node):
    """Test permit ws service."""

    await zha_client.send_json(
        {ID: 14, TYPE: f"{DOMAIN}/devices/{SERVICE_PERMIT}", **params}
    )

    msg = await zha_client.receive_json()
    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    assert app_controller.permit.await_count == 1
    assert app_controller.permit.await_args[1]["time_s"] == duration
    assert app_controller.permit.await_args[1]["node"] == node
    assert app_controller.permit_with_key.call_count == 0
