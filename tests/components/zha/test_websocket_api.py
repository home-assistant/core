"""Test ZHA WebSocket API."""

from __future__ import annotations

from binascii import unhexlify
from copy import deepcopy
from typing import TYPE_CHECKING
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

from freezegun import freeze_time
import pytest
import voluptuous as vol
import zigpy.backups
import zigpy.profiles.zha
import zigpy.types
from zigpy.types.named import EUI64
import zigpy.util
from zigpy.zcl.clusters import general, security
from zigpy.zcl.clusters.general import Groups
import zigpy.zdo.types as zdo_types

from homeassistant.components.websocket_api import const
from homeassistant.components.zha import DOMAIN
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
    ATTR_TYPE,
    BINDINGS,
    CLUSTER_TYPE_IN,
    EZSP_OVERWRITE_EUI64,
    GROUP_ID,
    GROUP_IDS,
    GROUP_NAME,
)
from homeassistant.components.zha.websocket_api import (
    ATTR_DURATION,
    ATTR_INSTALL_CODE,
    ATTR_QR_CODE,
    ATTR_SOURCE_IEEE,
    ATTR_TARGET_IEEE,
    ID,
    SERVICE_PERMIT,
    TYPE,
    async_load_api,
)
from homeassistant.const import ATTR_NAME, Platform
from homeassistant.core import Context, HomeAssistant

from .conftest import (
    FIXTURE_GRP_ID,
    FIXTURE_GRP_NAME,
    SIG_EP_INPUT,
    SIG_EP_OUTPUT,
    SIG_EP_PROFILE,
    SIG_EP_TYPE,
)
from .data import BASE_CUSTOM_CONFIGURATION, CONFIG_WITH_ALARM_OPTIONS

from tests.common import MockConfigEntry, MockUser

IEEE_SWITCH_DEVICE = "01:2d:6f:00:0a:90:69:e7"
IEEE_GROUPABLE_DEVICE = "01:2d:6f:00:0a:90:69:e8"

if TYPE_CHECKING:
    from zigpy.application import ControllerApplication


@pytest.fixture(autouse=True)
def required_platform_only():
    """Only set up the required and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.ALARM_CONTROL_PANEL,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
        ),
    ):
        yield


@pytest.fixture
async def device_switch(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA switch platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.OnOff.cluster_id, general.Basic.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            }
        },
        ieee=IEEE_SWITCH_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


@pytest.fixture
async def device_ias_ace(hass, zigpy_device_mock, zha_device_joined):
    """Test alarm control panel device."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [security.IasAce.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.IAS_ANCILLARY_CONTROL,
                SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            }
        },
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


@pytest.fixture
async def device_groupable(hass, zigpy_device_mock, zha_device_joined):
    """Test ZHA light platform."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.OnOff.cluster_id,
                    general.Basic.cluster_id,
                    general.Groups.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zigpy.profiles.zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zigpy.profiles.zha.PROFILE_ID,
            }
        },
        ieee=IEEE_GROUPABLE_DEVICE,
    )
    zha_device = await zha_device_joined(zigpy_device)
    zha_device.available = True
    return zha_device


@pytest.fixture
async def zha_client(hass, hass_ws_client, device_switch, device_groupable):
    """Get ZHA WebSocket client."""

    # load the ZHA API
    async_load_api(hass)
    return await hass_ws_client(hass)


async def test_device_clusters(hass: HomeAssistant, zha_client) -> None:
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


async def test_device_cluster_attributes(zha_client) -> None:
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
    assert len(attributes) == 7

    for attribute in attributes:
        assert attribute[ID] is not None
        assert attribute[ATTR_NAME] is not None


async def test_device_cluster_commands(zha_client) -> None:
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


@freeze_time("2023-09-23 20:16:00+00:00")
async def test_list_devices(zha_client) -> None:
    """Test getting ZHA devices."""
    await zha_client.send_json({ID: 5, TYPE: "zha/devices"})

    msg = await zha_client.receive_json()

    devices = msg["result"]
    assert len(devices) == 2 + 1  # the coordinator is included as well

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


async def test_get_zha_config(zha_client) -> None:
    """Test getting ZHA custom configuration."""
    await zha_client.send_json({ID: 5, TYPE: "zha/configuration"})

    msg = await zha_client.receive_json()

    configuration = msg["result"]
    assert configuration == BASE_CUSTOM_CONFIGURATION


async def test_get_zha_config_with_alarm(
    hass: HomeAssistant, zha_client, device_ias_ace
) -> None:
    """Test getting ZHA custom configuration."""
    await zha_client.send_json({ID: 5, TYPE: "zha/configuration"})

    msg = await zha_client.receive_json()

    configuration = msg["result"]
    assert configuration == CONFIG_WITH_ALARM_OPTIONS

    # test that the alarm options are not in the config when we remove the device
    device_ias_ace.gateway.device_removed(device_ias_ace.device)
    await hass.async_block_till_done()
    await zha_client.send_json({ID: 6, TYPE: "zha/configuration"})

    msg = await zha_client.receive_json()

    configuration = msg["result"]
    assert configuration == BASE_CUSTOM_CONFIGURATION


async def test_update_zha_config(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    zha_client,
    app_controller: ControllerApplication,
) -> None:
    """Test updating ZHA custom configuration."""
    configuration: dict = deepcopy(BASE_CUSTOM_CONFIGURATION)
    configuration["data"]["zha_options"]["default_light_transition"] = 10

    with patch(
        "bellows.zigbee.application.ControllerApplication.new",
        return_value=app_controller,
    ):
        await zha_client.send_json(
            {ID: 5, TYPE: "zha/configuration/update", "data": configuration["data"]}
        )
        msg = await zha_client.receive_json()
        assert msg["success"]

    await zha_client.send_json({ID: 6, TYPE: "zha/configuration"})
    msg = await zha_client.receive_json()
    test_configuration = msg["result"]
    assert test_configuration == configuration

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_device_not_found(zha_client) -> None:
    """Test not found response from get device API."""
    await zha_client.send_json(
        {ID: 6, TYPE: "zha/device", ATTR_IEEE: "28:6d:97:00:01:04:11:8c"}
    )
    msg = await zha_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND


async def test_list_groups(zha_client) -> None:
    """Test getting ZHA zigbee groups."""
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


async def test_get_group(zha_client) -> None:
    """Test getting a specific ZHA zigbee group."""
    await zha_client.send_json({ID: 8, TYPE: "zha/group", GROUP_ID: FIXTURE_GRP_ID})

    msg = await zha_client.receive_json()
    assert msg["id"] == 8
    assert msg["type"] == const.TYPE_RESULT

    group = msg["result"]
    assert group is not None
    assert group["group_id"] == FIXTURE_GRP_ID
    assert group["name"] == FIXTURE_GRP_NAME
    assert group["members"] == []


async def test_get_group_not_found(zha_client) -> None:
    """Test not found response from get group API."""
    await zha_client.send_json({ID: 9, TYPE: "zha/group", GROUP_ID: 1_234_567})

    msg = await zha_client.receive_json()

    assert msg["id"] == 9
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND


async def test_list_groupable_devices(
    zha_client, device_groupable, zigpy_app_controller
) -> None:
    """Test getting ZHA devices that have a group cluster."""
    # Ensure the coordinator doesn't have a group cluster
    coordinator = zigpy_app_controller.get_device(nwk=0x0000)
    del coordinator.endpoints[1].in_clusters[Groups.cluster_id]

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


async def test_add_group(zha_client) -> None:
    """Test adding and getting a new ZHA zigbee group."""
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


async def test_remove_group(zha_client) -> None:
    """Test removing a new ZHA zigbee group."""

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
async def app_controller(
    hass: HomeAssistant, setup_zha, zigpy_app_controller: ControllerApplication
) -> ControllerApplication:
    """Fixture for zigpy Application Controller."""
    await setup_zha()
    zigpy_app_controller.permit.reset_mock()
    return zigpy_app_controller


@pytest.mark.parametrize(
    ("params", "duration", "node"),
    [
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
    ],
)
async def test_permit_ha12(
    hass: HomeAssistant,
    app_controller: ControllerApplication,
    hass_admin_user: MockUser,
    params,
    duration,
    node,
) -> None:
    """Test permit service."""

    await hass.services.async_call(
        DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
    )
    assert app_controller.permit.await_count == 1
    assert app_controller.permit.await_args[1]["time_s"] == duration
    assert app_controller.permit.await_args[1]["node"] == node
    assert app_controller.permit_with_link_key.call_count == 0


IC_TEST_PARAMS = (
    (
        {
            ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
            ATTR_INSTALL_CODE: "5279-7BF4-A508-4DAA-8E17-12B6-1741-CA02-4051",
        },
        zigpy.types.EUI64.convert(IEEE_SWITCH_DEVICE),
        zigpy.util.convert_install_code(
            unhexlify("52797BF4A5084DAA8E1712B61741CA024051")
        ),
    ),
    (
        {
            ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
            ATTR_INSTALL_CODE: "52797BF4A5084DAA8E1712B61741CA024051",
        },
        zigpy.types.EUI64.convert(IEEE_SWITCH_DEVICE),
        zigpy.util.convert_install_code(
            unhexlify("52797BF4A5084DAA8E1712B61741CA024051")
        ),
    ),
)


@pytest.mark.parametrize(("params", "src_ieee", "code"), IC_TEST_PARAMS)
async def test_permit_with_install_code(
    hass: HomeAssistant,
    app_controller: ControllerApplication,
    hass_admin_user: MockUser,
    params,
    src_ieee,
    code,
) -> None:
    """Test permit service with install code."""

    await hass.services.async_call(
        DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
    )
    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_link_key.call_count == 1
    assert app_controller.permit_with_link_key.await_args[1]["time_s"] == 60
    assert app_controller.permit_with_link_key.await_args[1]["node"] == src_ieee
    assert app_controller.permit_with_link_key.await_args[1]["link_key"] == code


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
    hass: HomeAssistant,
    app_controller: ControllerApplication,
    hass_admin_user: MockUser,
    params,
) -> None:
    """Test permit service with install code."""

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
        )
    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_link_key.call_count == 0


IC_QR_CODE_TEST_PARAMS = (
    (
        {ATTR_QR_CODE: "000D6FFFFED4163B|52797BF4A5084DAA8E1712B61741CA024051"},
        zigpy.types.EUI64.convert("00:0D:6F:FF:FE:D4:16:3B"),
        zigpy.util.convert_install_code(
            unhexlify("52797BF4A5084DAA8E1712B61741CA024051")
        ),
    ),
    (
        {ATTR_QR_CODE: "Z:000D6FFFFED4163B$I:52797BF4A5084DAA8E1712B61741CA024051"},
        zigpy.types.EUI64.convert("00:0D:6F:FF:FE:D4:16:3B"),
        zigpy.util.convert_install_code(
            unhexlify("52797BF4A5084DAA8E1712B61741CA024051")
        ),
    ),
    (
        {
            ATTR_QR_CODE: (
                "G$M:751$S:357S00001579$D:000000000F350FFD%Z$A:04CF8CDF"
                "3C3C3C3C$I:52797BF4A5084DAA8E1712B61741CA024051"
            )
        },
        zigpy.types.EUI64.convert("04:CF:8C:DF:3C:3C:3C:3C"),
        zigpy.util.convert_install_code(
            unhexlify("52797BF4A5084DAA8E1712B61741CA024051")
        ),
    ),
    (
        {
            ATTR_QR_CODE: (
                "RB01SG"
                "0D836591B3CC0010000000000000000000"
                "000D6F0019107BB1"
                "DLK"
                "E4636CB6C41617C3E08F7325FFBFE1F9"
            )
        },
        zigpy.types.EUI64.convert("00:0D:6F:00:19:10:7B:B1"),
        zigpy.types.KeyData.convert("E4:63:6C:B6:C4:16:17:C3:E0:8F:73:25:FF:BF:E1:F9"),
    ),
)


@pytest.mark.parametrize(("params", "src_ieee", "code"), IC_QR_CODE_TEST_PARAMS)
async def test_permit_with_qr_code(
    hass: HomeAssistant,
    app_controller: ControllerApplication,
    hass_admin_user: MockUser,
    params,
    src_ieee,
    code,
) -> None:
    """Test permit service with install code from qr code."""

    await hass.services.async_call(
        DOMAIN, SERVICE_PERMIT, params, True, Context(user_id=hass_admin_user.id)
    )
    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_link_key.call_count == 1
    assert app_controller.permit_with_link_key.await_args[1]["time_s"] == 60
    assert app_controller.permit_with_link_key.await_args[1]["node"] == src_ieee
    assert app_controller.permit_with_link_key.await_args[1]["link_key"] == code


@pytest.mark.parametrize(("params", "src_ieee", "code"), IC_QR_CODE_TEST_PARAMS)
async def test_ws_permit_with_qr_code(
    app_controller: ControllerApplication, zha_client, params, src_ieee, code
) -> None:
    """Test permit service with install code from qr code."""

    await zha_client.send_json(
        {ID: 14, TYPE: f"{DOMAIN}/devices/{SERVICE_PERMIT}", **params}
    )

    msg_type = None
    while msg_type != const.TYPE_RESULT:
        # There will be logging events coming over the websocket
        # as well so we want to ignore those
        msg = await zha_client.receive_json()
        msg_type = msg["type"]

    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_link_key.call_count == 1
    assert app_controller.permit_with_link_key.await_args[1]["time_s"] == 60
    assert app_controller.permit_with_link_key.await_args[1]["node"] == src_ieee
    assert app_controller.permit_with_link_key.await_args[1]["link_key"] == code


@pytest.mark.parametrize("params", IC_FAIL_PARAMS)
async def test_ws_permit_with_install_code_fail(
    app_controller: ControllerApplication, zha_client, params
) -> None:
    """Test permit ws service with install code."""

    await zha_client.send_json(
        {ID: 14, TYPE: f"{DOMAIN}/devices/{SERVICE_PERMIT}", **params}
    )

    msg = await zha_client.receive_json()
    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"] is False

    assert app_controller.permit.await_count == 0
    assert app_controller.permit_with_link_key.call_count == 0


@pytest.mark.parametrize(
    ("params", "duration", "node"),
    [
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
    ],
)
async def test_ws_permit_ha12(
    app_controller: ControllerApplication, zha_client, params, duration, node
) -> None:
    """Test permit ws service."""

    await zha_client.send_json(
        {ID: 14, TYPE: f"{DOMAIN}/devices/{SERVICE_PERMIT}", **params}
    )

    msg_type = None
    while msg_type != const.TYPE_RESULT:
        # There will be logging events coming over the websocket
        # as well so we want to ignore those
        msg = await zha_client.receive_json()
        msg_type = msg["type"]

    assert msg["id"] == 14
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    assert app_controller.permit.await_count == 1
    assert app_controller.permit.await_args[1]["time_s"] == duration
    assert app_controller.permit.await_args[1]["node"] == node
    assert app_controller.permit_with_link_key.call_count == 0


async def test_get_network_settings(
    app_controller: ControllerApplication, zha_client
) -> None:
    """Test current network settings are returned."""

    await app_controller.backups.create_backup()

    await zha_client.send_json({ID: 6, TYPE: f"{DOMAIN}/network/settings"})
    msg = await zha_client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert "radio_type" in msg["result"]
    assert "network_info" in msg["result"]["settings"]
    assert "path" in msg["result"]["device"]


async def test_list_network_backups(
    app_controller: ControllerApplication, zha_client
) -> None:
    """Test backups are serialized."""

    await app_controller.backups.create_backup()

    await zha_client.send_json({ID: 6, TYPE: f"{DOMAIN}/network/backups/list"})
    msg = await zha_client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert "network_info" in msg["result"][0]


async def test_create_network_backup(
    app_controller: ControllerApplication, zha_client
) -> None:
    """Test creating backup."""

    assert not app_controller.backups.backups
    await zha_client.send_json({ID: 6, TYPE: f"{DOMAIN}/network/backups/create"})
    msg = await zha_client.receive_json()
    assert len(app_controller.backups.backups) == 1

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert "backup" in msg["result"] and "is_complete" in msg["result"]


async def test_restore_network_backup_success(
    app_controller: ControllerApplication, zha_client
) -> None:
    """Test successfully restoring a backup."""

    backup = zigpy.backups.NetworkBackup()

    with patch.object(app_controller.backups, "restore_backup", new=AsyncMock()) as p:
        await zha_client.send_json(
            {
                ID: 6,
                TYPE: f"{DOMAIN}/network/backups/restore",
                "backup": backup.as_dict(),
            }
        )
        msg = await zha_client.receive_json()

    p.assert_called_once_with(backup)
    assert "ezsp" not in backup.network_info.stack_specific

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]


async def test_restore_network_backup_force_write_eui64(
    app_controller: ControllerApplication, zha_client
) -> None:
    """Test successfully restoring a backup."""

    backup = zigpy.backups.NetworkBackup()

    with patch.object(app_controller.backups, "restore_backup", new=AsyncMock()) as p:
        await zha_client.send_json(
            {
                ID: 6,
                TYPE: f"{DOMAIN}/network/backups/restore",
                "backup": backup.as_dict(),
                "ezsp_force_write_eui64": True,
            }
        )
        msg = await zha_client.receive_json()

    # EUI64 will be overwritten
    p.assert_called_once_with(
        backup.replace(
            network_info=backup.network_info.replace(
                stack_specific={"ezsp": {EZSP_OVERWRITE_EUI64: True}}
            )
        )
    )

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]


@patch("zigpy.backups.NetworkBackup.from_dict", new=lambda v: v)
async def test_restore_network_backup_failure(
    app_controller: ControllerApplication, zha_client
) -> None:
    """Test successfully restoring a backup."""

    with patch.object(
        app_controller.backups,
        "restore_backup",
        new=AsyncMock(side_effect=ValueError("Restore failed")),
    ) as p:
        await zha_client.send_json(
            {ID: 6, TYPE: f"{DOMAIN}/network/backups/restore", "backup": "a backup"}
        )
        msg = await zha_client.receive_json()

    p.assert_called_once_with("a backup")

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_INVALID_FORMAT


@pytest.mark.parametrize("new_channel", ["auto", 15])
async def test_websocket_change_channel(
    new_channel: int | str, app_controller: ControllerApplication, zha_client
) -> None:
    """Test websocket API to migrate the network to a new channel."""

    with patch(
        "homeassistant.components.zha.websocket_api.async_change_channel",
        autospec=True,
    ) as change_channel_mock:
        await zha_client.send_json(
            {
                ID: 6,
                TYPE: f"{DOMAIN}/network/change_channel",
                "new_channel": new_channel,
            }
        )
        msg = await zha_client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    change_channel_mock.assert_has_calls([call(ANY, new_channel)])


@pytest.mark.parametrize(
    "operation",
    [("bind", zdo_types.ZDOCmd.Bind_req), ("unbind", zdo_types.ZDOCmd.Unbind_req)],
)
async def test_websocket_bind_unbind_devices(
    operation: tuple[str, zdo_types.ZDOCmd],
    app_controller: ControllerApplication,
    zha_client,
) -> None:
    """Test websocket API for binding and unbinding devices to devices."""

    command_type, req = operation
    with patch(
        "homeassistant.components.zha.websocket_api.async_binding_operation",
        autospec=True,
    ) as binding_operation_mock:
        await zha_client.send_json(
            {
                ID: 27,
                TYPE: f"zha/devices/{command_type}",
                ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
                ATTR_TARGET_IEEE: IEEE_GROUPABLE_DEVICE,
            }
        )
        msg = await zha_client.receive_json()

    assert msg["id"] == 27
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert binding_operation_mock.mock_calls == [
        call(
            ANY,
            EUI64.convert(IEEE_SWITCH_DEVICE),
            EUI64.convert(IEEE_GROUPABLE_DEVICE),
            req,
        )
    ]


@pytest.mark.parametrize("command_type", ["bind", "unbind"])
async def test_websocket_bind_unbind_group(
    command_type: str,
    hass: HomeAssistant,
    app_controller: ControllerApplication,
    zha_client,
) -> None:
    """Test websocket API for binding and unbinding devices to groups."""

    test_group_id = 0x0001
    gateway_mock = MagicMock()

    with patch(
        "homeassistant.components.zha.websocket_api.get_zha_gateway",
        return_value=gateway_mock,
    ):
        device_mock = MagicMock()
        bind_mock = AsyncMock()
        unbind_mock = AsyncMock()
        device_mock.async_bind_to_group = bind_mock
        device_mock.async_unbind_from_group = unbind_mock
        gateway_mock.get_device = MagicMock()
        gateway_mock.get_device.return_value = device_mock
        await zha_client.send_json(
            {
                ID: 27,
                TYPE: f"zha/groups/{command_type}",
                ATTR_SOURCE_IEEE: IEEE_SWITCH_DEVICE,
                GROUP_ID: test_group_id,
                BINDINGS: [
                    {
                        ATTR_ENDPOINT_ID: 1,
                        ID: 6,
                        ATTR_NAME: "OnOff",
                        ATTR_TYPE: "out",
                    },
                ],
            }
        )
        msg = await zha_client.receive_json()

    assert msg["id"] == 27
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    if command_type == "bind":
        assert bind_mock.mock_calls == [call(test_group_id, ANY)]
    elif command_type == "unbind":
        assert unbind_mock.mock_calls == [call(test_group_id, ANY)]
