"""Common test objects."""
import time
from unittest.mock import Mock

from asynctest import CoroutineMock
import zigpy.profiles.zha
import zigpy.types
import zigpy.zcl
import zigpy.zcl.clusters.general
import zigpy.zcl.foundation as zcl_f
import zigpy.zdo.types

from homeassistant.components.zha.core.const import (
    DATA_ZHA,
    DATA_ZHA_BRIDGE_ID,
    DATA_ZHA_CONFIG,
    DATA_ZHA_DISPATCHERS,
)
from homeassistant.util import slugify


class FakeApplication:
    """Fake application for mocking zigpy."""

    def __init__(self):
        """Init fake application."""
        self.ieee = zigpy.types.EUI64.convert("00:15:8d:00:02:32:4f:32")
        self.nwk = 0x087D


APPLICATION = FakeApplication()


class FakeEndpoint:
    """Fake endpoint for moking zigpy."""

    def __init__(self, manufacturer, model, epid=1):
        """Init fake endpoint."""
        self.device = None
        self.endpoint_id = epid
        self.in_clusters = {}
        self.out_clusters = {}
        self._cluster_attr = {}
        self.status = 1
        self.manufacturer = manufacturer
        self.model = model
        self.profile_id = zigpy.profiles.zha.PROFILE_ID
        self.device_type = None

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


def patch_cluster(cluster):
    """Patch a cluster for testing."""
    cluster.bind = CoroutineMock(return_value=[0])
    cluster.configure_reporting = CoroutineMock(return_value=[0])
    cluster.deserialize = Mock()
    cluster.handle_cluster_request = Mock()
    cluster.read_attributes = CoroutineMock()
    cluster.read_attributes_raw = Mock()
    cluster.unbind = CoroutineMock(return_value=[0])


class FakeDevice:
    """Fake device for mocking zigpy."""

    def __init__(self, ieee, manufacturer, model, node_desc=None):
        """Init fake device."""
        self._application = APPLICATION
        self.ieee = zigpy.types.EUI64.convert(ieee)
        self.nwk = 0xB79C
        self.zdo = Mock()
        self.endpoints = {0: self.zdo}
        self.lqi = 255
        self.rssi = 8
        self.last_seen = time.time()
        self.status = 2
        self.initializing = False
        self.manufacturer = manufacturer
        self.model = model
        self.node_desc = zigpy.zdo.types.NodeDescriptor()
        self.add_to_group = CoroutineMock()
        self.remove_from_group = CoroutineMock()
        if node_desc is None:
            node_desc = b"\x02@\x807\x10\x7fd\x00\x00*d\x00\x00"
        self.node_desc = zigpy.zdo.types.NodeDescriptor.deserialize(node_desc)[0]


def make_attribute(attrid, value, status=0):
    """Make an attribute."""
    attr = zcl_f.Attribute()
    attr.attrid = attrid
    attr.value = zcl_f.TypeValue()
    attr.value.value = value
    return attr


async def async_setup_entry(hass, config_entry):
    """Mock setup entry for zha."""
    hass.data[DATA_ZHA][DATA_ZHA_CONFIG] = {}
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS] = []
    hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID] = APPLICATION.ieee
    return True


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


async def async_enable_traffic(hass, zha_gateway, zha_devices):
    """Allow traffic to flow through the gateway and the zha device."""
    for zha_device in zha_devices:
        zha_device.update_available(True)
    await hass.async_block_till_done()


def make_zcl_header(command_id: int, global_command: bool = True) -> zcl_f.ZCLHeader:
    """Cluster.handle_message() ZCL Header helper."""
    if global_command:
        frc = zcl_f.FrameControl(zcl_f.FrameType.GLOBAL_COMMAND)
    else:
        frc = zcl_f.FrameControl(zcl_f.FrameType.CLUSTER_COMMAND)
    return zcl_f.ZCLHeader(frc, tsn=1, command_id=command_id)
