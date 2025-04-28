"""Common test objects."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import zigpy.zcl
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.zha.helpers import ZHADeviceProxy
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


def patch_cluster(cluster):
    """Patch a cluster for testing."""
    cluster.PLUGGED_ATTR_READS = {}

    async def _read_attribute_raw(attributes, *args, **kwargs):
        result = []
        for attr_id in attributes:
            value = cluster.PLUGGED_ATTR_READS.get(attr_id)
            if value is None:
                # try converting attr_id to attr_name and lookup the plugs again
                attr = cluster.attributes.get(attr_id)

                if attr is not None:
                    value = cluster.PLUGGED_ATTR_READS.get(attr.name)
            if value is not None:
                result.append(
                    zcl_f.ReadAttributeRecord(
                        attr_id,
                        zcl_f.Status.SUCCESS,
                        zcl_f.TypeValue(type=None, value=value),
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
    if not cluster.PLUGGED_ATTR_READS:
        return

    attrs = []
    for attrid, value in cluster.PLUGGED_ATTR_READS.items():
        if isinstance(attrid, str):
            attrid = cluster.attributes_by_name[attrid].id
        else:
            attrid = zigpy.types.uint16_t(attrid)
        attrs.append(make_attribute(attrid, value))

    hdr = make_zcl_header(zcl_f.GeneralCommand.Report_Attributes)
    hdr.frame_control.disable_default_response = True
    msg = zcl_f.GENERAL_COMMANDS[zcl_f.GeneralCommand.Report_Attributes].schema(
        attribute_reports=attrs
    )
    cluster.handle_message(hdr, msg)


def make_attribute(attrid, value, status=0):
    """Make an attribute."""
    attr = zcl_f.Attribute()
    attr.attrid = attrid
    attr.value = zcl_f.TypeValue()
    attr.value.value = value
    return attr


def send_attribute_report(hass: HomeAssistant, cluster, attrid, value):
    """Send a single attribute report."""
    return send_attributes_report(hass, cluster, {attrid: value})


async def send_attributes_report(
    hass: HomeAssistant, cluster: zigpy.zcl.Cluster, attributes: dict
):
    """Cause the sensor to receive an attribute report from the network.

    This is to simulate the normal device communication that happens when a
    device is paired to the zigbee network.
    """
    attrs = []

    for attrid, value in attributes.items():
        if isinstance(attrid, str):
            attrid = cluster.attributes_by_name[attrid].id
        else:
            attrid = zigpy.types.uint16_t(attrid)

        attrs.append(make_attribute(attrid, value))

    msg = zcl_f.GENERAL_COMMANDS[zcl_f.GeneralCommand.Report_Attributes].schema(
        attribute_reports=attrs
    )

    hdr = make_zcl_header(zcl_f.GeneralCommand.Report_Attributes)
    hdr.frame_control.disable_default_response = True
    cluster.handle_message(hdr, msg)
    await hass.async_block_till_done()


def find_entity_id(
    domain: str, zha_device: ZHADeviceProxy, hass: HomeAssistant, qualifier=None
) -> str | None:
    """Find the entity id under the testing.

    This is used to get the entity id in order to get the state from the state
    machine so that we can test state changes.
    """
    entities = find_entity_ids(domain, zha_device, hass)
    if not entities:
        return None
    if qualifier:
        for entity_id in entities:
            if qualifier in entity_id:
                return entity_id
        return None
    return entities[0]


def find_entity_ids(
    domain: str, zha_device: ZHADeviceProxy, hass: HomeAssistant
) -> list[str]:
    """Find the entity ids under the testing.

    This is used to get the entity id in order to get the state from the state
    machine so that we can test state changes.
    """

    registry = er.async_get(hass)
    return [
        entity.entity_id
        for entity in er.async_entries_for_device(registry, zha_device.device_id)
        if entity.domain == domain
    ]


def async_find_group_entity_id(hass: HomeAssistant, domain, group):
    """Find the group entity id under test."""
    entity_id = f"{domain}.coordinator_manufacturer_coordinator_model_{group.name.lower().replace(' ', '_')}"

    entity_ids = hass.states.async_entity_ids(domain)
    assert entity_id in entity_ids
    return entity_id


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


async def async_shift_time(hass: HomeAssistant):
    """Shift time to cause call later tasks to run."""
    next_update = dt_util.utcnow() + timedelta(seconds=11)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
