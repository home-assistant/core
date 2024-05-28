"""Test ZHA firmware updates."""

from unittest.mock import AsyncMock, call, patch

import pytest
from zigpy.exceptions import DeliveryError
from zigpy.ota import OtaImageWithMetadata
import zigpy.ota.image as firmware
from zigpy.ota.providers import BaseOtaImageMetadata
from zigpy.profiles import zha
import zigpy.types as t
from zigpy.zcl import foundation
from zigpy.zcl.clusters import general

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from .common import async_enable_traffic, find_entity_id, update_attribute_cache
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_TYPE


@pytest.fixture(autouse=True)
def update_platform_only():
    """Only set up the update and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.UPDATE,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
        ),
    ):
        yield


@pytest.fixture
def zigpy_device(zigpy_device_mock):
    """Device tracker zigpy device."""
    endpoints = {
        1: {
            SIG_EP_INPUT: [general.Basic.cluster_id, general.OnOff.cluster_id],
            SIG_EP_OUTPUT: [general.Ota.cluster_id],
            SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
        }
    }
    return zigpy_device_mock(
        endpoints, node_descriptor=b"\x02@\x84_\x11\x7fd\x00\x00,d\x00\x00"
    )


async def setup_test_data(
    zha_device_joined_restored,
    zigpy_device,
    skip_attribute_plugs=False,
    file_not_found=False,
):
    """Set up test data for the tests."""
    fw_version = 0x12345678
    installed_fw_version = fw_version - 10
    cluster = zigpy_device.endpoints[1].out_clusters[general.Ota.cluster_id]
    if not skip_attribute_plugs:
        cluster.PLUGGED_ATTR_READS = {
            general.Ota.AttributeDefs.current_file_version.name: installed_fw_version
        }
        update_attribute_cache(cluster)

    # set up firmware image
    fw_image = OtaImageWithMetadata(
        metadata=BaseOtaImageMetadata(
            file_version=fw_version,
            manufacturer_id=0x1234,
            image_type=0x90,
            changelog="This is a test firmware image!",
        ),
        firmware=firmware.OTAImage(
            header=firmware.OTAImageHeader(
                upgrade_file_id=firmware.OTAImageHeader.MAGIC_VALUE,
                file_version=fw_version,
                image_type=0x90,
                manufacturer_id=0x1234,
                header_version=256,
                header_length=56,
                field_control=0,
                stack_version=2,
                header_string="This is a test header!",
                image_size=56 + 2 + 4 + 8,
            ),
            subelements=[firmware.SubElement(tag_id=0x0000, data=b"fw_image")],
        ),
    )

    cluster.endpoint.device.application.ota.get_ota_image = AsyncMock(
        return_value=None if file_not_found else fw_image
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    zha_device.async_update_sw_build_id(installed_fw_version)

    return zha_device, cluster, fw_image, installed_fw_version


async def test_firmware_update_notification_from_zigpy(
    hass: HomeAssistant,
    zha_device_joined_restored,
    zigpy_device,
) -> None:
    """Test ZHA update platform - firmware update notification."""
    zha_device, cluster, fw_image, installed_fw_version = await setup_test_data(
        zha_device_joined_restored,
        zigpy_device,
    )

    entity_id = find_entity_id(Platform.UPDATE, zha_device, hass)
    assert entity_id is not None

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    assert hass.states.get(entity_id).state == STATE_OFF

    # simulate an image available notification
    await cluster._handle_query_next_image(
        foundation.ZCLHeader.cluster(
            tsn=0x12, command_id=general.Ota.ServerCommandDefs.query_next_image.id
        ),
        general.QueryNextImageCommand(
            fw_image.firmware.header.field_control,
            zha_device.manufacturer_code,
            fw_image.firmware.header.image_type,
            installed_fw_version,
            fw_image.firmware.header.header_version,
        ),
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == f"0x{installed_fw_version:08x}"
    assert not attrs[ATTR_IN_PROGRESS]
    assert (
        attrs[ATTR_LATEST_VERSION] == f"0x{fw_image.firmware.header.file_version:08x}"
    )


async def test_firmware_update_notification_from_service_call(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device
) -> None:
    """Test ZHA update platform - firmware update manual check."""
    zha_device, cluster, fw_image, installed_fw_version = await setup_test_data(
        zha_device_joined_restored, zigpy_device
    )

    entity_id = find_entity_id(Platform.UPDATE, zha_device, hass)
    assert entity_id is not None

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    assert hass.states.get(entity_id).state == STATE_OFF

    async def _async_image_notify_side_effect(*args, **kwargs):
        await cluster._handle_query_next_image(
            foundation.ZCLHeader.cluster(
                tsn=0x12, command_id=general.Ota.ServerCommandDefs.query_next_image.id
            ),
            general.QueryNextImageCommand(
                fw_image.firmware.header.field_control,
                zha_device.manufacturer_code,
                fw_image.firmware.header.image_type,
                installed_fw_version,
                fw_image.firmware.header.header_version,
            ),
        )

    await async_setup_component(hass, HA_DOMAIN, {})
    with patch(
        "zigpy.ota.OTA.broadcast_notify", side_effect=_async_image_notify_side_effect
    ):
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            service_data={ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        assert cluster.endpoint.device.application.ota.broadcast_notify.await_count == 1
        assert cluster.endpoint.device.application.ota.broadcast_notify.call_args_list[
            0
        ] == call(
            jitter=100,
        )

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        attrs = state.attributes
        assert attrs[ATTR_INSTALLED_VERSION] == f"0x{installed_fw_version:08x}"
        assert not attrs[ATTR_IN_PROGRESS]
        assert (
            attrs[ATTR_LATEST_VERSION]
            == f"0x{fw_image.firmware.header.file_version:08x}"
        )


def make_packet(zigpy_device, cluster, cmd_name: str, **kwargs):
    """Make a zigpy packet."""
    req_hdr, req_cmd = cluster._create_request(
        general=False,
        command_id=cluster.commands_by_name[cmd_name].id,
        schema=cluster.commands_by_name[cmd_name].schema,
        disable_default_response=False,
        direction=foundation.Direction.Client_to_Server,
        args=(),
        kwargs=kwargs,
    )

    return t.ZigbeePacket(
        src=t.AddrModeAddress(addr_mode=t.AddrMode.NWK, address=zigpy_device.nwk),
        src_ep=1,
        dst=t.AddrModeAddress(addr_mode=t.AddrMode.NWK, address=0x0000),
        dst_ep=1,
        tsn=req_hdr.tsn,
        profile_id=260,
        cluster_id=cluster.cluster_id,
        data=t.SerializableBytes(req_hdr.serialize() + req_cmd.serialize()),
        lqi=255,
        rssi=-30,
    )


@patch("zigpy.device.AFTER_OTA_ATTR_READ_DELAY", 0.01)
async def test_firmware_update_success(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device
) -> None:
    """Test ZHA update platform - firmware update success."""
    zha_device, cluster, fw_image, installed_fw_version = await setup_test_data(
        zha_device_joined_restored, zigpy_device
    )

    assert installed_fw_version < fw_image.firmware.header.file_version

    entity_id = find_entity_id(Platform.UPDATE, zha_device, hass)
    assert entity_id is not None

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    assert hass.states.get(entity_id).state == STATE_OFF

    # simulate an image available notification
    await cluster._handle_query_next_image(
        foundation.ZCLHeader.cluster(
            tsn=0x12, command_id=general.Ota.ServerCommandDefs.query_next_image.id
        ),
        general.QueryNextImageCommand(
            field_control=fw_image.firmware.header.field_control,
            manufacturer_code=zha_device.manufacturer_code,
            image_type=fw_image.firmware.header.image_type,
            current_file_version=installed_fw_version,
        ),
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == f"0x{installed_fw_version:08x}"
    assert not attrs[ATTR_IN_PROGRESS]
    assert (
        attrs[ATTR_LATEST_VERSION] == f"0x{fw_image.firmware.header.file_version:08x}"
    )

    async def endpoint_reply(cluster_id, tsn, data, command_id):
        if cluster_id == general.Ota.cluster_id:
            hdr, cmd = cluster.deserialize(data)
            if isinstance(cmd, general.Ota.ImageNotifyCommand):
                zigpy_device.packet_received(
                    make_packet(
                        zigpy_device,
                        cluster,
                        general.Ota.ServerCommandDefs.query_next_image.name,
                        field_control=general.Ota.QueryNextImageCommand.FieldControl.HardwareVersion,
                        manufacturer_code=fw_image.firmware.header.manufacturer_id,
                        image_type=fw_image.firmware.header.image_type,
                        current_file_version=fw_image.firmware.header.file_version - 10,
                        hardware_version=1,
                    )
                )
            elif isinstance(
                cmd, general.Ota.ClientCommandDefs.query_next_image_response.schema
            ):
                assert cmd.status == foundation.Status.SUCCESS
                assert cmd.manufacturer_code == fw_image.firmware.header.manufacturer_id
                assert cmd.image_type == fw_image.firmware.header.image_type
                assert cmd.file_version == fw_image.firmware.header.file_version
                assert cmd.image_size == fw_image.firmware.header.image_size
                zigpy_device.packet_received(
                    make_packet(
                        zigpy_device,
                        cluster,
                        general.Ota.ServerCommandDefs.image_block.name,
                        field_control=general.Ota.ImageBlockCommand.FieldControl.RequestNodeAddr,
                        manufacturer_code=fw_image.firmware.header.manufacturer_id,
                        image_type=fw_image.firmware.header.image_type,
                        file_version=fw_image.firmware.header.file_version,
                        file_offset=0,
                        maximum_data_size=40,
                        request_node_addr=zigpy_device.ieee,
                    )
                )
            elif isinstance(
                cmd, general.Ota.ClientCommandDefs.image_block_response.schema
            ):
                if cmd.file_offset == 0:
                    assert cmd.status == foundation.Status.SUCCESS
                    assert (
                        cmd.manufacturer_code
                        == fw_image.firmware.header.manufacturer_id
                    )
                    assert cmd.image_type == fw_image.firmware.header.image_type
                    assert cmd.file_version == fw_image.firmware.header.file_version
                    assert cmd.file_offset == 0
                    assert cmd.image_data == fw_image.firmware.serialize()[0:40]
                    zigpy_device.packet_received(
                        make_packet(
                            zigpy_device,
                            cluster,
                            general.Ota.ServerCommandDefs.image_block.name,
                            field_control=general.Ota.ImageBlockCommand.FieldControl.RequestNodeAddr,
                            manufacturer_code=fw_image.firmware.header.manufacturer_id,
                            image_type=fw_image.firmware.header.image_type,
                            file_version=fw_image.firmware.header.file_version,
                            file_offset=40,
                            maximum_data_size=40,
                            request_node_addr=zigpy_device.ieee,
                        )
                    )
                elif cmd.file_offset == 40:
                    assert cmd.status == foundation.Status.SUCCESS
                    assert (
                        cmd.manufacturer_code
                        == fw_image.firmware.header.manufacturer_id
                    )
                    assert cmd.image_type == fw_image.firmware.header.image_type
                    assert cmd.file_version == fw_image.firmware.header.file_version
                    assert cmd.file_offset == 40
                    assert cmd.image_data == fw_image.firmware.serialize()[40:70]

                    # make sure the state machine gets progress reports
                    state = hass.states.get(entity_id)
                    assert state.state == STATE_ON
                    attrs = state.attributes
                    assert (
                        attrs[ATTR_INSTALLED_VERSION] == f"0x{installed_fw_version:08x}"
                    )
                    assert attrs[ATTR_IN_PROGRESS] == 58
                    assert (
                        attrs[ATTR_LATEST_VERSION]
                        == f"0x{fw_image.firmware.header.file_version:08x}"
                    )

                    zigpy_device.packet_received(
                        make_packet(
                            zigpy_device,
                            cluster,
                            general.Ota.ServerCommandDefs.upgrade_end.name,
                            status=foundation.Status.SUCCESS,
                            manufacturer_code=fw_image.firmware.header.manufacturer_id,
                            image_type=fw_image.firmware.header.image_type,
                            file_version=fw_image.firmware.header.file_version,
                        )
                    )

            elif isinstance(
                cmd, general.Ota.ClientCommandDefs.upgrade_end_response.schema
            ):
                assert cmd.manufacturer_code == fw_image.firmware.header.manufacturer_id
                assert cmd.image_type == fw_image.firmware.header.image_type
                assert cmd.file_version == fw_image.firmware.header.file_version
                assert cmd.current_time == 0
                assert cmd.upgrade_time == 0

                def read_new_fw_version(*args, **kwargs):
                    cluster.update_attribute(
                        attrid=general.Ota.AttributeDefs.current_file_version.id,
                        value=fw_image.firmware.header.file_version,
                    )
                    return {
                        general.Ota.AttributeDefs.current_file_version.id: (
                            fw_image.firmware.header.file_version
                        )
                    }, {}

                cluster.read_attributes.side_effect = read_new_fw_version

    cluster.endpoint.reply = AsyncMock(side_effect=endpoint_reply)
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    attrs = state.attributes
    assert (
        attrs[ATTR_INSTALLED_VERSION]
        == f"0x{fw_image.firmware.header.file_version:08x}"
    )
    assert not attrs[ATTR_IN_PROGRESS]
    assert attrs[ATTR_LATEST_VERSION] == attrs[ATTR_INSTALLED_VERSION]

    # If we send a progress notification incorrectly, it won't be handled
    entity = hass.data[UPDATE_DOMAIN].get_entity(entity_id)
    entity._update_progress(50, 100, 0.50)

    state = hass.states.get(entity_id)
    assert not attrs[ATTR_IN_PROGRESS]
    assert state.state == STATE_OFF


async def test_firmware_update_raises(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device
) -> None:
    """Test ZHA update platform - firmware update raises."""
    zha_device, cluster, fw_image, installed_fw_version = await setup_test_data(
        zha_device_joined_restored, zigpy_device
    )

    entity_id = find_entity_id(Platform.UPDATE, zha_device, hass)
    assert entity_id is not None

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    assert hass.states.get(entity_id).state == STATE_OFF

    # simulate an image available notification
    await cluster._handle_query_next_image(
        foundation.ZCLHeader.cluster(
            tsn=0x12, command_id=general.Ota.ServerCommandDefs.query_next_image.id
        ),
        general.QueryNextImageCommand(
            fw_image.firmware.header.field_control,
            zha_device.manufacturer_code,
            fw_image.firmware.header.image_type,
            installed_fw_version,
            fw_image.firmware.header.header_version,
        ),
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == f"0x{installed_fw_version:08x}"
    assert not attrs[ATTR_IN_PROGRESS]
    assert (
        attrs[ATTR_LATEST_VERSION] == f"0x{fw_image.firmware.header.file_version:08x}"
    )

    async def endpoint_reply(cluster_id, tsn, data, command_id):
        if cluster_id == general.Ota.cluster_id:
            hdr, cmd = cluster.deserialize(data)
            if isinstance(cmd, general.Ota.ImageNotifyCommand):
                zigpy_device.packet_received(
                    make_packet(
                        zigpy_device,
                        cluster,
                        general.Ota.ServerCommandDefs.query_next_image.name,
                        field_control=general.Ota.QueryNextImageCommand.FieldControl.HardwareVersion,
                        manufacturer_code=fw_image.firmware.header.manufacturer_id,
                        image_type=fw_image.firmware.header.image_type,
                        current_file_version=fw_image.firmware.header.file_version - 10,
                        hardware_version=1,
                    )
                )
            elif isinstance(
                cmd, general.Ota.ClientCommandDefs.query_next_image_response.schema
            ):
                assert cmd.status == foundation.Status.SUCCESS
                assert cmd.manufacturer_code == fw_image.firmware.header.manufacturer_id
                assert cmd.image_type == fw_image.firmware.header.image_type
                assert cmd.file_version == fw_image.firmware.header.file_version
                assert cmd.image_size == fw_image.firmware.header.image_size
                raise DeliveryError("failed to deliver")

    cluster.endpoint.reply = AsyncMock(side_effect=endpoint_reply)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    with (
        patch(
            "zigpy.device.Device.update_firmware",
            AsyncMock(side_effect=DeliveryError("failed to deliver")),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )


async def test_firmware_update_no_longer_compatible(
    hass: HomeAssistant, zha_device_joined_restored, zigpy_device
) -> None:
    """Test ZHA update platform - firmware update is no longer valid."""
    zha_device, cluster, fw_image, installed_fw_version = await setup_test_data(
        zha_device_joined_restored, zigpy_device
    )

    entity_id = find_entity_id(Platform.UPDATE, zha_device, hass)
    assert entity_id is not None

    # allow traffic to flow through the gateway and device
    await async_enable_traffic(hass, [zha_device])

    assert hass.states.get(entity_id).state == STATE_OFF

    # simulate an image available notification
    await cluster._handle_query_next_image(
        foundation.ZCLHeader.cluster(
            tsn=0x12, command_id=general.Ota.ServerCommandDefs.query_next_image.id
        ),
        general.QueryNextImageCommand(
            fw_image.firmware.header.field_control,
            zha_device.manufacturer_code,
            fw_image.firmware.header.image_type,
            installed_fw_version,
            fw_image.firmware.header.header_version,
        ),
    )

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == f"0x{installed_fw_version:08x}"
    assert not attrs[ATTR_IN_PROGRESS]
    assert (
        attrs[ATTR_LATEST_VERSION] == f"0x{fw_image.firmware.header.file_version:08x}"
    )

    new_version = 0x99999999

    async def endpoint_reply(cluster_id, tsn, data, command_id):
        if cluster_id == general.Ota.cluster_id:
            hdr, cmd = cluster.deserialize(data)
            if isinstance(cmd, general.Ota.ImageNotifyCommand):
                zigpy_device.packet_received(
                    make_packet(
                        zigpy_device,
                        cluster,
                        general.Ota.ServerCommandDefs.query_next_image.name,
                        field_control=general.Ota.QueryNextImageCommand.FieldControl.HardwareVersion,
                        manufacturer_code=fw_image.firmware.header.manufacturer_id,
                        image_type=fw_image.firmware.header.image_type,
                        # The device reports that it is no longer compatible!
                        current_file_version=new_version,
                        hardware_version=1,
                    )
                )

    cluster.endpoint.reply = AsyncMock(side_effect=endpoint_reply)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: entity_id,
            },
            blocking=True,
        )

    # We updated the currently installed firmware version, as it is no longer valid
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    attrs = state.attributes
    assert attrs[ATTR_INSTALLED_VERSION] == f"0x{new_version:08x}"
    assert not attrs[ATTR_IN_PROGRESS]
    assert attrs[ATTR_LATEST_VERSION] == f"0x{new_version:08x}"
