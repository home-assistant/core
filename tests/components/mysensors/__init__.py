"""Test MySensors component."""
from enum import IntEnum
from unittest.mock import MagicMock

import voluptuous as vol

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


class MessageType(IntEnum):
    """MySensors message types."""

    # pylint: disable=too-few-public-methods
    presentation = 0
    set = 1
    req = 2
    internal = 3
    stream = 4


class Presentation(IntEnum):
    """MySensors presentation sub-types."""

    # pylint: disable=too-few-public-methods
    S_BINARY = 3
    S_DIMMER = 4
    S_TEMP = 6
    S_LIGHT_LEVEL = 16
    S_SOUND = 33
    S_VIBRATION = 34


class SetReq(IntEnum):
    """MySensors set/req sub-types."""

    # pylint: disable=too-few-public-methods
    V_TEMP = 0
    V_HUM = 1
    V_STATUS = 2
    V_LIGHT = 2
    V_PERCENTAGE = 3
    V_DIMMER = 3
    V_PRESSURE = 4
    V_FORECAST = 5
    V_RAIN = 6
    V_RAINRATE = 7
    V_WIND = 8
    V_GUST = 9
    V_DIRECTION = 10
    V_UV = 11
    V_WEIGHT = 12
    V_DISTANCE = 13
    V_IMPEDANCE = 14
    V_ARMED = 15
    V_TRIPPED = 16
    V_WATT = 17
    V_KWH = 18
    V_SCENE_ON = 19
    V_SCENE_OFF = 20
    V_HVAC_FLOW_STATE = 21
    V_HVAC_SPEED = 22
    V_LIGHT_LEVEL = 23
    V_VAR1 = 24
    V_VAR2 = 25
    V_VAR3 = 26
    V_VAR4 = 27
    V_VAR5 = 28
    V_UP = 29
    V_DOWN = 30
    V_STOP = 31
    V_IR_SEND = 32
    V_IR_RECEIVE = 33
    V_FLOW = 34
    V_VOLUME = 35
    V_LOCK_STATUS = 36
    V_LEVEL = 37
    V_DUST_LEVEL = 37
    V_VOLTAGE = 38
    V_CURRENT = 39
    V_RGB = 40
    V_RGBW = 41
    V_ID = 42
    V_UNIT_PREFIX = 43
    V_HVAC_SETPOINT_COOL = 44
    V_HVAC_SETPOINT_HEAT = 45
    V_HVAC_FLOW_MODE = 46
    V_TEXT = 47
    V_CUSTOM = 48
    V_POSITION = 49
    V_IR_RECORD = 50
    V_PH = 51
    V_ORP = 52
    V_EC = 53
    V_VAR = 54
    V_VA = 55
    V_POWER_FACTOR = 56


class Internal(IntEnum):
    """MySensors internal sub-types."""

    # pylint: disable=too-few-public-methods
    I_GATEWAY_READY = 14


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
        self.const.MessageType = MessageType
        self.const.Presentation = Presentation
        self.const.SetReq = SetReq
        self.const.Internal = Internal
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
