"""Test MySensors component."""
from unittest.mock import MagicMock

import voluptuous as vol
from mysensors import const_22 as const

from homeassistant.components import mysensors as mysensors_comp
from homeassistant.setup import async_setup_component
from tests.common import mock_coro_func

DEVICE = '/dev/ttyACM0'


def get_gateway(hass):
    """Helper to get a gateway from set up gateways."""
    gateways = hass.data[mysensors_comp.MYSENSORS_GATEWAYS]
    gateway = next(iter(gateways.values()))
    return gateway


async def setup_mysensors(hass):
    """Set up mysensors."""
    config = {'mysensors': {
        'gateways': [{'device': DEVICE}],
        'version': '2.0', 'persistence': False}}

    res = await async_setup_component(hass, 'mysensors', config)
    return res


class MockGateway(MagicMock):
    """Mock a MySensors gateway."""

    def __init__(self, *args, event_callback=None, persistence=False,
                 persistence_file='mysensors.pickle', protocol_version='1.4',
                 **kwargs):
        """Initialize a MySensors mock gateway."""
        super().__init__()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True
        self.persistence = persistence
        self.persistence_file = persistence_file
        self.protocol_version = protocol_version
        self.const = MagicMock()
        self.ota = MagicMock()
        self.const.MessageType = const.MessageType
        self.const.Presentation = const.Presentation
        self.const.SetReq = const.SetReq
        self.const.Internal = const.Internal
        self.start = mock_coro_func()
        self.start_persistence = mock_coro_func()


class MockMQTTGateway(MockGateway):
    """Mock a MySensors MQTT gateway."""

    # pylint: disable=too-many-ancestors

    def __init__(self, pub_callback, sub_callback, *args, **kwargs):
        """Initialize a MySensors mock MQTT gateway."""
        super().__init__(*args, **kwargs)
        self.pub_callback = pub_callback
        self.sub_callback = sub_callback


class MockNode(MagicMock):
    """Mock a MySensors node."""

    def __init__(
            self, node_id, node_type=None, sketch_name='mock sketch',
            sketch_version='1.0', protocol_version='1.4'):
        """Initialize a MySensors mock node."""
        super().__init__()
        self.sensor_id = node_id
        self.children = {}
        self.type = node_type
        self.sketch_name = sketch_name
        self.sketch_version = sketch_version
        self.battery_level = 0
        self.protocol_version = protocol_version


class MockChild(MagicMock):
    """Mock a MySensors child."""

    def __init__(self, child_id, child_type, description=''):
        """Initialize a MySensors mock child."""
        # pylint: disable=invalid-name
        super().__init__()
        self.id = child_id
        self.type = child_type
        self.description = description
        self.values = {}

    def get_schema(self, protocol_version):
        """Return a voluptuous schema."""
        # pylint: disable=no-self-use
        return vol.Schema({})


class MockMessage(MagicMock):
    """Mock a MySensors message."""

    def __init__(
            self, node_id=0, child_id=0, message_type=0, ack=0, sub_type=0,
            payload='', gateway=None):
        """Set up message."""
        super().__init__()
        self.node_id = node_id
        self.child_id = child_id
        self.type = message_type
        self.ack = ack
        self.sub_type = sub_type
        self.payload = payload
        self.gateway = gateway
