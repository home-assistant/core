"""Common test objects."""
import time
from unittest.mock import Mock

from asynctest import CoroutineMock
from zigpy.device import Device as zigpy_dev
from zigpy.endpoint import Endpoint as zigpy_ep
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl
import zigpy.zcl.clusters.general
import zigpy.zcl.foundation as zcl_f
import zigpy.zdo.types

import homeassistant.components.zha.core.const as zha_const
from homeassistant.util import slugify


class FakeEndpoint:
    """Fake endpoint for moking zigpy."""

    def __init__(self, manufacturer, model, epid=1):
        """Init fake endpoint."""
        self.device = None
        self.endpoint_id = epid
        self.in_clusters = {}
        self.out_clusters = {}
        self._cluster_attr = {}
        self.member_of = {}
        self.status = 1
        self.manufacturer = manufacturer
        self.model = model
        self.profile_id = zigpy.profiles.zha.PROFILE_ID
        self.device_type = None
        self.request = CoroutineMock()

    def add_input_cluster(self, cluster_id):
        """Add an input cluster."""
        cluster = zigpy.zcl.Cluster.from_id(self, cluster_id, is_server=True)
        patch_cluster(cluster)
        self.in_clusters[cluster_id] = cluster
        if hasattr(cluster, "ep_attribute"):
            setattr(self, cluster.ep_attribute, cluster)

    def add_output_cluster(self, cluster_id):
        """Add an output cluster."""
        cluster = zigpy.zcl.Cluster.from_id(self, cluster_id, is_server=False)
        patch_cluster(cluster)
        self.out_clusters[cluster_id] = cluster

    @property
    def __class__(self):
        """Fake being Zigpy endpoint."""
        return zigpy_ep

    @property
    def unique_id(self):
        """Return the unique id for the endpoint."""
        return self.device.ieee, self.endpoint_id


FakeEndpoint.add_to_group = zigpy_ep.add_to_group


def patch_cluster(cluster):
    """Patch a cluster for testing."""
    cluster.bind = CoroutineMock(return_value=[0])
    cluster.configure_reporting = CoroutineMock(return_value=[0])
    cluster.deserialize = Mock()
    cluster.handle_cluster_request = Mock()
    cluster.read_attributes = CoroutineMock(return_value=[{}, {}])
    cluster.read_attributes_raw = Mock()
    cluster.unbind = CoroutineMock(return_value=[0])
    cluster.write_attributes = CoroutineMock(return_value=[0])
    if cluster.cluster_id == 4:
        cluster.add = CoroutineMock(return_value=[0])


class FakeDevice:
    """Fake device for mocking zigpy."""

    def __init__(self, app, ieee, manufacturer, model, node_desc=None, nwk=0xB79C):
        """Init fake device."""
        self._application = app
        self.application = app
        self.ieee = zigpy.types.EUI64.convert(ieee)
        self.nwk = nwk
        self.zdo = Mock()
        self.endpoints = {0: self.zdo}
        self.lqi = 255
        self.rssi = 8
        self.last_seen = time.time()
        self.status = 2
        self.initializing = False
        self.skip_configuration = False
        self.manufacturer = manufacturer
        self.model = model
        self.node_desc = zigpy.zdo.types.NodeDescriptor()
        self.remove_from_group = CoroutineMock()
        if node_desc is None:
            node_desc = b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00"
        self.node_desc = zigpy.zdo.types.NodeDescriptor.deserialize(node_desc)[0]


FakeDevice.add_to_group = zigpy_dev.add_to_group


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


async def send_attributes_report(hass, cluster: int, attributes: dict):
    """Cause the sensor to receive an attribute report from the network.

    This is to simulate the normal device communication that happens when a
    device is paired to the zigbee network.
    """
    attrs = [make_attribute(attrid, value) for attrid, value in attributes.items()]
    hdr = make_zcl_header(zcl_f.Command.Report_Attributes)
    cluster.handle_message(hdr, [attrs])
    await hass.async_block_till_done()


async def find_entity_id(domain, zha_device, hass):
    """Find the entity id under the testing.

    This is used to get the entity id in order to get the state from the state
    machine so that we can test state changes.
    """
    ieeetail = "".join([f"{o:02x}" for o in zha_device.ieee[:4]])
    head = f"{domain}." + slugify(f"{zha_device.name} {ieeetail}")

    enitiy_ids = hass.states.async_entity_ids(domain)
    await hass.async_block_till_done()

    for entity_id in enitiy_ids:
        if entity_id.startswith(head):
            return entity_id
    return None


def async_find_group_entity_id(hass, domain, group):
    """Find the group entity id under test."""
    entity_id = f"{domain}.{group.name.lower().replace(' ','_')}_zha_group_0x{group.group_id:04x}"

    entity_ids = hass.states.async_entity_ids(domain)

    if entity_id in entity_ids:
        return entity_id
    return None


async def async_enable_traffic(hass, zha_devices):
    """Allow traffic to flow through the gateway and the zha device."""
    for zha_device in zha_devices:
        zha_device.update_available(True)
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
        assert cluster.configure_reporting.call_count == reports
        assert cluster.configure_reporting.await_count == reports
