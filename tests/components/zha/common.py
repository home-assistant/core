"""Common test objects."""
import time
from unittest.mock import Mock
from homeassistant.components.zha.core.helpers import convert_ieee
from homeassistant.components.zha.core.const import (
    DATA_ZHA, DATA_ZHA_CONFIG, DATA_ZHA_DISPATCHERS, DATA_ZHA_BRIDGE_ID
)
from homeassistant.util import slugify


class FakeApplication:
    """Fake application for mocking zigpy."""

    def __init__(self):
        """Init fake application."""
        self.ieee = convert_ieee("00:15:8d:00:02:32:4f:32")
        self.nwk = 0x087d


APPLICATION = FakeApplication()


class FakeEndpoint:
    """Fake endpoint for moking zigpy."""

    def __init__(self):
        """Init fake endpoint."""
        from zigpy.profiles.zha import PROFILE_ID
        self.device = None
        self.endpoint_id = 1
        self.in_clusters = {}
        self.out_clusters = {}
        self._cluster_attr = {}
        self.status = 1
        self.manufacturer = 'FakeManufacturer'
        self.model = 'FakeModel'
        self.profile_id = PROFILE_ID
        self.device_type = None

    def add_input_cluster(self, cluster_id):
        """Add an input cluster."""
        from zigpy.zcl import Cluster
        cluster = Cluster.from_id(self, cluster_id)
        patch_cluster(cluster)
        self.in_clusters[cluster_id] = cluster
        if hasattr(cluster, 'ep_attribute'):
            setattr(self, cluster.ep_attribute, cluster)

    def add_output_cluster(self, cluster_id):
        """Add an output cluster."""
        from zigpy.zcl import Cluster
        cluster = Cluster.from_id(self, cluster_id)
        patch_cluster(cluster)
        self.out_clusters[cluster_id] = cluster


def patch_cluster(cluster):
    """Patch a cluster for testing."""
    cluster.deserialize = Mock()
    cluster.handle_cluster_request = Mock()
    cluster.handle_cluster_general_request = Mock()
    cluster.read_attributes_raw = Mock()
    cluster.read_attributes = Mock()
    cluster.write_attributes = Mock()
    cluster.bind = Mock()
    cluster.unbind = Mock()
    cluster.configure_reporting = Mock()


class FakeDevice:
    """Fake device for mocking zigpy."""

    def __init__(self):
        """Init fake device."""
        self._application = APPLICATION
        self.ieee = convert_ieee("00:0d:6f:00:0a:90:69:e7")
        self.nwk = 0xb79c
        self.zdo = Mock()
        self.endpoints = {0: self.zdo}
        self.lqi = 255
        self.rssi = 8
        self.last_seen = time.time()
        self.status = 2
        self.initializing = False
        self.manufacturer = 'FakeManufacturer'
        self.model = 'FakeModel'


def make_device(in_cluster_ids, out_cluster_ids, device_type):
    """Make a fake device using the specified cluster classes."""
    device = FakeDevice()
    endpoint = FakeEndpoint()
    endpoint.device = device
    device.endpoints[endpoint.endpoint_id] = endpoint
    endpoint.device_type = device_type

    for cluster_id in in_cluster_ids:
        endpoint.add_input_cluster(cluster_id)

    for cluster_id in out_cluster_ids:
        endpoint.add_output_cluster(cluster_id)

    return device


async def async_init_zigpy_device(
        in_cluster_ids, out_cluster_ids, device_type, gateway, hass):
    """Create and initialize a device."""
    device = make_device(in_cluster_ids, out_cluster_ids, device_type)
    await gateway.async_device_initialized(device, False)
    await hass.async_block_till_done()
    return device


def make_attribute(attrid, value, status=0):
    """Make an attribute."""
    from zigpy.zcl.foundation import Attribute, TypeValue
    attr = Attribute()
    attr.attrid = attrid
    attr.value = TypeValue()
    attr.value.value = value
    return attr


async def async_setup_entry(hass, config_entry):
    """Mock setup entry for zha."""
    hass.data[DATA_ZHA][DATA_ZHA_CONFIG] = {}
    hass.data[DATA_ZHA][DATA_ZHA_DISPATCHERS] = []
    hass.data[DATA_ZHA][DATA_ZHA_BRIDGE_ID] = APPLICATION.ieee
    return True


def make_entity_id(domain, device, cluster):
    """Make the entity id for the entity under testing."""
    ieee = device.ieee
    ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
    entity_id = "{}.{}_{}_{}_{}{}".format(
        domain,
        slugify(device.manufacturer),
        slugify(device.model),
        ieeetail,
        cluster.endpoint.endpoint_id,
        "_{}".format(cluster.cluster_id),
    )
    return entity_id


async def async_enable_traffic(hass, zha_gateway, zha_device):
    """Allow traffic to flow through the gateway and the zha device."""
    await zha_gateway.accept_zigbee_messages({})
    zha_device.update_available(True)
    await hass.async_block_till_done()
