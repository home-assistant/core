"""Test ZHA button."""

from typing import Final
from unittest.mock import call, patch

from freezegun import freeze_time
import pytest
from zhaquirks.const import (
    DEVICE_TYPE,
    ENDPOINTS,
    INPUT_CLUSTERS,
    OUTPUT_CLUSTERS,
    PROFILE_ID,
)
from zhaquirks.tuya.ts0601_valve import ParksideTuyaValveManufCluster
from zigpy.const import SIG_EP_PROFILE
from zigpy.exceptions import ZigbeeException
from zigpy.profiles import zha
from zigpy.quirks import CustomCluster, CustomDevice
from zigpy.quirks.v2 import add_to_registry_v2
import zigpy.types as t
from zigpy.zcl.clusters import general, security
from zigpy.zcl.clusters.manufacturer_specific import ManufacturerSpecificCluster
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.button import DOMAIN, SERVICE_PRESS, ButtonDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import find_entity_id, update_attribute_cache
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def button_platform_only():
    """Only set up the button and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.DEVICE_TRACKER,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
        ),
    ):
        yield


@pytest.fixture
async def contact_sensor(
    hass: HomeAssistant, zigpy_device_mock, zha_device_joined_restored
):
    """Contact sensor fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.Identify.cluster_id,
                    security.IasZone.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_ZONE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    return zha_device, zigpy_device.endpoints[1].identify


class FrostLockQuirk(CustomDevice):
    """Quirk with frost lock attribute."""

    class TuyaManufCluster(CustomCluster, ManufacturerSpecificCluster):
        """Tuya manufacturer specific cluster."""

        cluster_id = 0xEF00
        ep_attribute = "tuya_manufacturer"

        attributes = {0xEF01: ("frost_lock_reset", t.Bool)}

    replacement = {
        ENDPOINTS: {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                INPUT_CLUSTERS: [general.Basic.cluster_id, TuyaManufCluster],
                OUTPUT_CLUSTERS: [],
            },
        }
    }


@pytest.fixture
async def tuya_water_valve(
    hass: HomeAssistant, zigpy_device_mock, zha_device_joined_restored
):
    """Tuya Water Valve fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                PROFILE_ID: zha.PROFILE_ID,
                DEVICE_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                INPUT_CLUSTERS: [
                    general.Basic.cluster_id,
                    general.Identify.cluster_id,
                    general.Groups.cluster_id,
                    general.Scenes.cluster_id,
                    general.OnOff.cluster_id,
                    ParksideTuyaValveManufCluster.cluster_id,
                ],
                OUTPUT_CLUSTERS: [general.Time.cluster_id, general.Ota.cluster_id],
            },
        },
        manufacturer="_TZE200_htnnfasr",
        model="TS0601",
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    return zha_device, zigpy_device.endpoints[1].tuya_manufacturer


@freeze_time("2021-11-04 17:37:00", tz_offset=-1)
async def test_button(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, contact_sensor
) -> None:
    """Test ZHA button platform."""

    zha_device, cluster = contact_sensor
    assert cluster is not None
    entity_id = find_entity_id(DOMAIN, zha_device, hass)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.IDENTIFY

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.DIAGNOSTIC

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0
        assert cluster.request.call_args[0][3] == 5  # duration in seconds

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2021-11-04T16:37:00+00:00"
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.IDENTIFY


async def test_frost_unlock(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, tuya_water_valve
) -> None:
    """Test custom frost unlock ZHA button."""

    zha_device, cluster = tuya_water_valve
    assert cluster is not None
    entity_id = find_entity_id(DOMAIN, zha_device, hass, qualifier="frost_lock_reset")
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.RESTART

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.entity_category == EntityCategory.CONFIG

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert cluster.write_attributes.mock_calls == [
            call({"frost_lock_reset": 0}, manufacturer=None)
        ]

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == ButtonDeviceClass.RESTART

    cluster.write_attributes.reset_mock()
    cluster.write_attributes.side_effect = ZigbeeException

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # There are three retries
    assert cluster.write_attributes.mock_calls == [
        call({"frost_lock_reset": 0}, manufacturer=None),
        call({"frost_lock_reset": 0}, manufacturer=None),
        call({"frost_lock_reset": 0}, manufacturer=None),
    ]


class FakeManufacturerCluster(CustomCluster, ManufacturerSpecificCluster):
    """Fake manufacturer cluster."""

    cluster_id: Final = 0xFFF3
    ep_attribute: Final = "mfg_identify"

    class AttributeDefs(zcl_f.BaseAttributeDefs):
        """Attribute definitions."""

        feed: Final = zcl_f.ZCLAttributeDef(
            id=0x0000, type=t.uint8_t, access="rw", is_manufacturer_specific=True
        )

    class ServerCommandDefs(zcl_f.BaseCommandDefs):
        """Server command definitions."""

        self_test: Final = zcl_f.ZCLCommandDef(
            id=0x00, schema={"identify_time": t.uint16_t}, direction=False
        )


(
    add_to_registry_v2("Fake_Model", "Fake_Manufacturer")
    .replaces(FakeManufacturerCluster)
    .command_button(
        FakeManufacturerCluster.ServerCommandDefs.self_test.name,
        FakeManufacturerCluster.cluster_id,
        command_args=(5,),
    )
    .write_attr_button(
        FakeManufacturerCluster.AttributeDefs.feed.name,
        2,
        FakeManufacturerCluster.cluster_id,
    )
)


@pytest.fixture
async def custom_button_device(
    hass: HomeAssistant, zigpy_device_mock, zha_device_joined_restored
):
    """Button device fixture for quirks button tests."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    FakeManufacturerCluster.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.REMOTE_CONTROL,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        manufacturer="Fake_Model",
        model="Fake_Manufacturer",
    )

    zigpy_device.endpoints[1].mfg_identify.PLUGGED_ATTR_READS = {
        FakeManufacturerCluster.AttributeDefs.feed.name: 0,
    }
    update_attribute_cache(zigpy_device.endpoints[1].mfg_identify)
    zha_device = await zha_device_joined_restored(zigpy_device)
    return zha_device, zigpy_device.endpoints[1].mfg_identify


@freeze_time("2021-11-04 17:37:00", tz_offset=-1)
async def test_quirks_command_button(hass: HomeAssistant, custom_button_device) -> None:
    """Test ZHA button platform."""

    zha_device, cluster = custom_button_device
    assert cluster is not None
    entity_id = find_entity_id(DOMAIN, zha_device, hass, qualifier="self_test")
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args[0][0] is False
        assert cluster.request.call_args[0][1] == 0
        assert cluster.request.call_args[0][3] == 5  # duration in seconds

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2021-11-04T16:37:00+00:00"


@freeze_time("2021-11-04 17:37:00", tz_offset=-1)
async def test_quirks_write_attr_button(
    hass: HomeAssistant, custom_button_device
) -> None:
    """Test ZHA button platform."""

    zha_device, cluster = custom_button_device
    assert cluster is not None
    entity_id = find_entity_id(DOMAIN, zha_device, hass, qualifier="feed")
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert cluster.get(cluster.AttributeDefs.feed.name) == 0

    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert cluster.write_attributes.mock_calls == [
            call({cluster.AttributeDefs.feed.name: 2}, manufacturer=None)
        ]

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2021-11-04T16:37:00+00:00"
    assert cluster.get(cluster.AttributeDefs.feed.name) == 2
