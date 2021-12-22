"""Common test objects."""
import asyncio
import math
from unittest.mock import AsyncMock, Mock

import zigpy.zcl
import zigpy.zcl.foundation as zcl_f

import homeassistant.components.zha.core.const as zha_const
from homeassistant.util import slugify


def patch_cluster(cluster):
    """Patch a cluster for testing."""
    cluster.PLUGGED_ATTR_READS = {}

    async def _read_attribute_raw(attributes, *args, **kwargs):
        result = []
        for attr_id in attributes:
            value = cluster.PLUGGED_ATTR_READS.get(attr_id)
            if value is None:
                # try converting attr_id to attr_name and lookup the plugs again
                attr_name = cluster.attributes.get(attr_id)
                value = attr_name and cluster.PLUGGED_ATTR_READS.get(attr_name[0])
            if value is not None:
                result.append(
                    zcl_f.ReadAttributeRecord(
                        attr_id,
                        zcl_f.Status.SUCCESS,
                        zcl_f.TypeValue(python_type=None, value=value),
                    )
                )
            else:
                result.append(zcl_f.ReadAttributeRecord(attr_id, zcl_f.Status.FAILURE))
        return (result,)

    cluster.bind = AsyncMock(return_value=[0])
    cluster.configure_reporting = AsyncMock(
        return_value=[
            [zcl_f.ConfigureReportingResponseRecord(zcl_f.Status.SUCCESS, 0x00, 0xAABB)]
        ]
    )
    cluster.configure_reporting_multiple = AsyncMock(
        return_value=zcl_f.ConfigureReportingResponse.deserialize(b"\x00")[0]
    )
    cluster.deserialize = Mock()
    cluster.handle_cluster_request = Mock()
    cluster.read_attributes = AsyncMock(wraps=cluster.read_attributes)
    cluster.read_attributes_raw = AsyncMock(side_effect=_read_attribute_raw)
    cluster.unbind = AsyncMock(return_value=[0])
    cluster.write_attributes = AsyncMock(wraps=cluster.write_attributes)
    cluster._write_attributes = AsyncMock(
        return_value=[zcl_f.WriteAttributesResponse.deserialize(b"\x00")[0]]
    )
    if cluster.cluster_id == 4:
        cluster.add = AsyncMock(return_value=[0])


def update_attribute_cache(cluster):
    """Update attribute cache based on plugged attributes."""
    if cluster.PLUGGED_ATTR_READS:
        attrs = [
            make_attribute(cluster.attridx.get(attr, attr), value)
            for attr, value in cluster.PLUGGED_ATTR_READS.items()
        ]
        hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
        hdr.frame_control.disable_default_response = True
        cluster.handle_message(hdr, [attrs])


def get_zha_gateway(hass):
    """Return ZHA gateway from hass.data."""
    try:
        return hass.data[zha_const.DATA_ZHA][zha_const.DATA_ZHA_GATEWAY]
    except KeyError:
        return None


def make_attribute(attrid, value, status=0):
    """Make an attribute."""
    attr = zcl_f.Attribute()
    attr.attrid = attrid
    attr.value = zcl_f.TypeValue()
    attr.value.value = value
    return attr


def send_attribute_report(hass, cluster, attrid, value):
    """Send a single attribute report."""
    return send_attributes_report(hass, cluster, {attrid: value})


async def send_attributes_report(hass, cluster: zigpy.zcl.Cluster, attributes: dict):
    """Cause the sensor to receive an attribute report from the network.

    This is to simulate the normal device communication that happens when a
    device is paired to the zigbee network.
    """
    attrs = [
        make_attribute(cluster.attridx.get(attr, attr), value)
        for attr, value in attributes.items()
    ]
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    hdr.frame_control.disable_default_response = True
    cluster.handle_message(hdr, [attrs])
    await hass.async_block_till_done()


async def find_entity_id(domain, zha_device, hass, qualifier=None):
    """Find the entity id under the testing.

    This is used to get the entity id in order to get the state from the state
    machine so that we can test state changes.
    """
    entities = await find_entity_ids(domain, zha_device, hass)
    if not entities:
        return None
    if qualifier:
        for entity_id in entities:
            if qualifier in entity_id:
                return entity_id
    else:
        return entities[0]


async def find_entity_ids(domain, zha_device, hass):
    """Find the entity ids under the testing.

    This is used to get the entity id in order to get the state from the state
    machine so that we can test state changes.
    """
    ieeetail = "".join([f"{o:02x}" for o in zha_device.ieee[:4]])
    head = f"{domain}.{slugify(f'{zha_device.name} {ieeetail}')}"

    enitiy_ids = hass.states.async_entity_ids(domain)
    await hass.async_block_till_done()

    res = []
    for entity_id in enitiy_ids:
        if entity_id.startswith(head):
            res.append(entity_id)
    return res


def async_find_group_entity_id(hass, domain, group):
    """Find the group entity id under test."""
    entity_id = f"{domain}.{group.name.lower().replace(' ','_')}_zha_group_0x{group.group_id:04x}"

    entity_ids = hass.states.async_entity_ids(domain)

    if entity_id in entity_ids:
        return entity_id
    return None


async def async_enable_traffic(hass, zha_devices, enabled=True):
    """Allow traffic to flow through the gateway and the zha device."""
    for zha_device in zha_devices:
        zha_device.update_available(enabled)
    await hass.async_block_till_done()


def make_zcl_header(
    command_id: int, global_command: bool = True, tsn: int = 1
) -> zcl_f.ZCLHeader:
    """Cluster.handle_message() ZCL Header helper."""
    if global_command:
        frc = zcl_f.FrameControl(zcl_f.FrameType.GLOBAL_COMMAND)
    else:
        frc = zcl_f.FrameControl(zcl_f.FrameType.CLUSTER_COMMAND)
    return zcl_f.ZCLHeader(frc, tsn=tsn, command_id=command_id)


def reset_clusters(clusters):
    """Reset mocks on cluster."""
    for cluster in clusters:
        cluster.bind.reset_mock()
        cluster.configure_reporting.reset_mock()
        cluster.configure_reporting_multiple.reset_mock()
        cluster.write_attributes.reset_mock()


async def async_test_rejoin(hass, zigpy_device, clusters, report_counts, ep_id=1):
    """Test device rejoins."""
    reset_clusters(clusters)

    zha_gateway = get_zha_gateway(hass)
    await zha_gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done()
    for cluster, reports in zip(clusters, report_counts):
        assert cluster.bind.call_count == 1
        assert cluster.bind.await_count == 1
        if reports:
            assert cluster.configure_reporting.call_count == 0
            assert cluster.configure_reporting.await_count == 0
            assert cluster.configure_reporting_multiple.call_count == math.ceil(
                reports / zha_const.REPORT_CONFIG_ATTR_PER_REQ
            )
            assert cluster.configure_reporting_multiple.await_count == math.ceil(
                reports / zha_const.REPORT_CONFIG_ATTR_PER_REQ
            )
        else:
            # no reports at all
            assert cluster.configure_reporting.call_count == reports
            assert cluster.configure_reporting.await_count == reports
            assert cluster.configure_reporting_multiple.call_count == reports
            assert cluster.configure_reporting_multiple.await_count == reports


async def async_wait_for_updates(hass):
    """Wait until all scheduled updates are executed."""
    await hass.async_block_till_done()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await hass.async_block_till_done()
