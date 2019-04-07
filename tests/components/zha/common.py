"""Common test objects."""
import time
from unittest.mock import patch, Mock
from homeassistant.components.zha.core.helpers import convert_ieee
from homeassistant.components.zha.core.const import (
    DATA_ZHA, DATA_ZHA_CONFIG, DATA_ZHA_DISPATCHERS, DATA_ZHA_BRIDGE_ID
)
from homeassistant.util import slugify
from tests.common import mock_coro


class FakeApplication:
    """Fake application for mocking zigpy."""

    def __init__(self):
        """Init fake application."""
        self.ieee = convert_ieee("00:15:8d:00:02:32:4f:32")
        self.nwk = 0x087d


APPLICATION = FakeApplication()


class FakeEndpoint:
    """Fake endpoint for moking zigpy."""

    def __init__(self, manufacturer, model):
        """Init fake endpoint."""
        from zigpy.profiles.zha import PROFILE_ID
        self.device = None
        self.endpoint_id = 1
        self.in_clusters = {}
        self.out_clusters = {}
        self._cluster_attr = {}
        self.status = 1
        self.manufacturer = manufacturer
        self.model = model
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
    cluster.unbind = Mock()


class FakeDevice:
    """Fake device for mocking zigpy."""

    def __init__(self, ieee, manufacturer, model):
        """Init fake device."""
        self._application = APPLICATION
        self.ieee = convert_ieee(ieee)
        self.nwk = 0xb79c
        self.zdo = Mock()
        self.endpoints = {0: self.zdo}
        self.lqi = 255
        self.rssi = 8
        self.last_seen = time.time()
        self.status = 2
        self.initializing = False
        self.manufacturer = manufacturer
        self.model = model


def make_device(in_cluster_ids, out_cluster_ids, device_type, ieee,
                manufacturer, model):
    """Make a fake device using the specified cluster classes."""
    device = FakeDevice(ieee, manufacturer, model)
    endpoint = FakeEndpoint(manufacturer, model)
    endpoint.device = device
    device.endpoints[endpoint.endpoint_id] = endpoint
    endpoint.device_type = device_type

    for cluster_id in in_cluster_ids:
        endpoint.add_input_cluster(cluster_id)

    for cluster_id in out_cluster_ids:
        endpoint.add_output_cluster(cluster_id)

    return device


async def async_init_zigpy_device(
        hass, in_cluster_ids, out_cluster_ids, device_type, gateway,
        ieee="00:0d:6f:00:0a:90:69:e7", manufacturer="FakeManufacturer",
        model="FakeModel", is_new_join=False):
    """Create and initialize a device.

    This creates a fake device and adds it to the "network". It can be used to
    test existing device functionality and new device pairing functionality.
    The is_new_join parameter influences whether or not the device will go
    through cluster binding and zigbee cluster configure reporting. That only
    happens when the device is paired to the network for the first time.
    """
    device = make_device(in_cluster_ids, out_cluster_ids, device_type, ieee,
                         manufacturer, model)
    await gateway.async_device_initialized(device, is_new_join)
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


def make_entity_id(domain, device, cluster, use_suffix=True):
    """Make the entity id for the entity under testing.

    This is used to get the entity id in order to get the state from the state
    machine so that we can test state changes.
    """
    ieee = device.ieee
    ieeetail = ''.join(['%02x' % (o, ) for o in ieee[-4:]])
    entity_id = "{}.{}_{}_{}_{}{}".format(
        domain,
        slugify(device.manufacturer),
        slugify(device.model),
        ieeetail,
        cluster.endpoint.endpoint_id,
        ("", "_{}".format(cluster.cluster_id))[use_suffix],
    )
    return entity_id


async def async_enable_traffic(hass, zha_gateway, zha_devices):
    """Allow traffic to flow through the gateway and the zha device."""
    for zha_device in zha_devices:
        zha_device.update_available(True)
    await hass.async_block_till_done()


async def async_test_device_join(
        hass, zha_gateway, cluster_id, domain, device_type=None):
    """Test a newly joining device.

    This creates a new fake device and adds it to the network. It is meant to
    simulate pairing a new device to the network so that code pathways that
    only trigger during device joins can be tested.
    """
    from zigpy.zcl.foundation import Status
    from zigpy.zcl.clusters.general import Basic
    # create zigpy device mocking out the zigbee network operations
    with patch(
            'zigpy.zcl.Cluster.configure_reporting',
            return_value=mock_coro([Status.SUCCESS, Status.SUCCESS])):
        with patch(
                'zigpy.zcl.Cluster.bind',
                return_value=mock_coro([Status.SUCCESS, Status.SUCCESS])):
            zigpy_device = await async_init_zigpy_device(
                hass, [cluster_id, Basic.cluster_id], [], device_type,
                zha_gateway,
                ieee="00:0d:6f:00:0a:90:69:f7",
                manufacturer="FakeMan{}".format(cluster_id),
                model="FakeMod{}".format(cluster_id),
                is_new_join=True)
            cluster = zigpy_device.endpoints.get(1).in_clusters[cluster_id]
            entity_id = make_entity_id(
                domain, zigpy_device, cluster, use_suffix=device_type is None)
            assert hass.states.get(entity_id) is not None
