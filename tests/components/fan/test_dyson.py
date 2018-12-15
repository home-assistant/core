"""Test the Dyson fan component."""
import unittest
from unittest import mock

from homeassistant.setup import setup_component
from homeassistant.components import dyson as dyson_parent
from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.components.fan import (dyson, ATTR_SPEED, ATTR_SPEED_LIST,
                                          ATTR_OSCILLATING)
from tests.common import get_test_home_assistant
from libpurecool.const import FanSpeed, FanMode, NightMode, Oscillation
from libpurecool.dyson_pure_state import DysonPureCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureCoolV2State
from libpurecool.dyson_pure_cool_link import DysonPureCoolLink
from libpurecool.dyson_pure_cool import DysonPureCool


class MockDysonState(DysonPureCoolState):
    """Mock Dyson state."""

    def __init__(self):
        """Create new Mock Dyson State."""
        pass


class MockDysonV2State(DysonPureCoolV2State):
    """Mock Dyson purecool v2 state."""

    def __init__(self):
        """Create new Mock Dyson purecool v2 state."""
        pass


def _get_device_with_no_state():
    """Return a device with no state."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = None
    return device


def _get_device_off():
    """Return a device with state off."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.fan_mode = "OFF"
    device.state.night_mode = "ON"
    device.state.speed = "0004"
    return device


def _get_device_auto():
    """Return a device with state auto."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.fan_mode = "AUTO"
    device.state.night_mode = "ON"
    device.state.speed = "AUTO"
    return device


def _get_device_on():
    """Return a valid state on."""
    device = mock.Mock(spec=DysonPureCoolLink)
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.fan_mode = "FAN"
    device.state.fan_state = "FAN"
    device.state.oscillation = "ON"
    device.state.night_mode = "OFF"
    device.state.speed = "0001"
    return device


def _get_purecool_device_auto():
    """Return a purecool device with state auto."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.fan_mode = "AUTO"
    device.state.night_mode = "ON"
    device.state.speed = "AUTO"
    device.state.auto_mode = "ON"
    return device


def _get_purecool_device_on():
    """Return a valid state on."""
    device = mock.Mock(spec=DysonPureCool)
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.oscillation = "OION"
    device.state.speed = "1"
    device.state.fan_power = "ON"
    device.state.front_direction = 'ON'
    device.state.oscillation_angle_low = "0090"
    device.state.oscillation_angle_high = "0180"
    device.state.sleep_timer = 60
    return device


def _get_purecool_device_off():
    """Return a device with state off."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.fan_mode = "OFF"
    device.state.night_mode = "ON"
    device.state.speed = "0004"
    device.state.oscillation = "OIOFF"
    device.state.front_direction = "OFF"
    device.state.sleep_timer = "OFF"
    return device


class DysonTest(unittest.TestCase):
    """Dyson Sensor component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_with_no_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_entities = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_entities)
        add_entities.assert_called_with([])

    def test_setup_component(self):
        """Test setup component with devices."""
        def _add_device(devices):
            assert len(devices) == 2
            assert devices[0].name == "Device_name"

        device_fan = _get_device_on()
        device_purecool_fan = _get_purecool_device_on()
        device_non_fan = _get_device_off()

        self.hass.data[dyson.DYSON_DEVICES] = [device_fan,
                                               device_purecool_fan,
                                               device_non_fan]
        dyson.setup_platform(self.hass, None, _add_device)

    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_device_on()])
    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_get_state_attributes(self, mocked_login, mocked_devices):
        """Test async added to hass."""
        setup_component(self.hass, dyson_parent.DOMAIN, {
            dyson_parent.DOMAIN: {
                dyson_parent.CONF_USERNAME: "email",
                dyson_parent.CONF_PASSWORD: "password",
                dyson_parent.CONF_LANGUAGE: "US",
                }
            })
        self.hass.block_till_done()
        state = self.hass.states.get("{}.{}".format(
            dyson.DOMAIN,
            mocked_devices.return_value[0].name))

        assert dyson.ATTR_NIGHT_MODE in state.attributes
        assert dyson.ATTR_AUTO_MODE in state.attributes
        assert ATTR_SPEED in state.attributes
        assert ATTR_SPEED_LIST in state.attributes
        assert ATTR_OSCILLATING in state.attributes

    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_device_on()])
    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_async_added_to_hass(self, mocked_login, mocked_devices):
        """Test async added to hass."""
        setup_component(self.hass, dyson_parent.DOMAIN, {
            dyson_parent.DOMAIN: {
                dyson_parent.CONF_USERNAME: "email",
                dyson_parent.CONF_PASSWORD: "password",
                dyson_parent.CONF_LANGUAGE: "US",
                }
            })
        self.hass.block_till_done()
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 1
        assert mocked_devices.return_value[0].add_message_listener.called

    def test_dyson_set_speed(self):
        """Test set fan speed."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.set_speed("1")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN,
                                      fan_speed=FanSpeed.FAN_SPEED_1)

        component.set_speed("AUTO")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.AUTO)

    def test_dyson_turn_on(self):
        """Test turn on fan."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.turn_on()
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN)

    def test_dyson_turn_night_mode(self):
        """Test turn on fan with night mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.set_night_mode(True)
        set_config = device.set_configuration
        set_config.assert_called_with(night_mode=NightMode.NIGHT_MODE_ON)

        component.set_night_mode(False)
        set_config = device.set_configuration
        set_config.assert_called_with(night_mode=NightMode.NIGHT_MODE_OFF)

    def test_is_night_mode(self):
        """Test night mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.night_mode

        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.night_mode

    def test_dyson_turn_auto_mode(self):
        """Test turn on/off fan with auto mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.set_auto_mode(True)
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.AUTO)

        component.set_auto_mode(False)
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN)

    def test_is_auto_mode(self):
        """Test auto mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.auto_mode

        device = _get_device_auto()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.auto_mode

    def test_dyson_turn_on_speed(self):
        """Test turn on fan with specified speed."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.turn_on("1")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN,
                                      fan_speed=FanSpeed.FAN_SPEED_1)

        component.turn_on("AUTO")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.AUTO)

    def test_dyson_turn_off(self):
        """Test turn off fan."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.turn_off()
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.OFF)

    def test_dyson_oscillate_off(self):
        """Test turn off oscillation."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        component.oscillate(False)
        set_config = device.set_configuration
        set_config.assert_called_with(oscillation=Oscillation.OSCILLATION_OFF)

    def test_dyson_oscillate_on(self):
        """Test turn on oscillation."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        component.oscillate(True)
        set_config = device.set_configuration
        set_config.assert_called_with(oscillation=Oscillation.OSCILLATION_ON)

    def test_dyson_oscillate_value_on(self):
        """Test get oscillation value on."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.oscillating

    def test_dyson_oscillate_value_off(self):
        """Test get oscillation value off."""
        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.oscillating

    def test_dyson_on(self):
        """Test device is on."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.is_on

    def test_dyson_off(self):
        """Test device is off."""
        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.is_on

        device = _get_device_with_no_state()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.is_on

    def test_dyson_get_speed(self):
        """Test get device speed."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.speed == 1

        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.speed == 4

        device = _get_device_with_no_state()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.speed is None

        device = _get_device_auto()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.speed == "AUTO"

    def test_dyson_get_direction(self):
        """Test get device direction."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.current_direction is None

    def test_dyson_get_speed_list(self):
        """Test get speeds list."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert len(component.speed_list) == 11

    def test_dyson_supported_features(self):
        """Test supported features."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.supported_features == 3

    def test_on_message(self):
        """Test when message is received."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        component.entity_id = "entity_id"
        component.schedule_update_ha_state = mock.Mock()
        component.on_message(MockDysonState())
        component.schedule_update_ha_state.assert_called_with()

    def test_service_set_night_mode(self):
        """Test set night mode service."""
        dyson_device = mock.MagicMock()
        self.hass.data[DYSON_DEVICES] = []
        dyson_device.entity_id = 'fan.living_room'
        self.hass.data[dyson.DYSON_FAN_DEVICES] = [dyson_device]
        dyson.setup_platform(self.hass, None, mock.MagicMock())

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_NIGHT_MODE,
                                {"entity_id": "fan.bed_room",
                                 "night_mode": True}, True)
        assert not dyson_device.set_night_mode.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_NIGHT_MODE,
                                {"entity_id": "fan.living_room",
                                 "night_mode": True}, True)
        dyson_device.set_night_mode.assert_called_with(True)

    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_purecool_device_on()])
    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_async_purecool_added_to_hass(self, mocked_login, mocked_devices):
        """Test async added to hass."""
        setup_component(self.hass, dyson_parent.DOMAIN, {
            dyson_parent.DOMAIN: {
                dyson_parent.CONF_USERNAME: "email",
                dyson_parent.CONF_PASSWORD: "password",
                dyson_parent.CONF_LANGUAGE: "US",
                }
            })
        self.hass.block_till_done()
        assert len(self.hass.data[dyson.DYSON_DEVICES]) == 1
        assert mocked_devices.return_value[0].add_message_listener.called

    def test_dyson_purecool_turn_on(self):
        """Test turn on purecool fan."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.turn_on()
        set_config = device.turn_on
        set_config.assert_called_with()

    def test_dyson_purecool_set_night_mode(self):
        """Test turn on fan with night mode."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.set_night_mode(True)
        set_config = device.enable_night_mode
        set_config.assert_called_with()

        component.set_night_mode(False)
        set_config = device.disable_night_mode
        set_config.assert_called_with()

    def test_night_mode(self):
        """Test night mode."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.night_mode

        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.night_mode

    def test_dyson_purecool_set_auto_mode(self):
        """Test turn on/off purecool fan with auto mode."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.set_auto_mode(True)
        set_config = device.enable_auto_mode
        set_config.assert_called_with()

        component.set_auto_mode(False)
        set_config = device.disable_auto_mode
        set_config.assert_called_with()

    def test_auto_mode(self):
        """Test purecool auto mode."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.auto_mode

        device = _get_purecool_device_auto()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.auto_mode

    def test_dyson_purecool_turn_on_speed(self):
        """Test turn on fan with specified speed."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.turn_on("1")
        set_config = device.set_fan_speed
        set_config.assert_called_with(FanSpeed.FAN_SPEED_1)

        component.turn_on("AUTO")
        set_config = device.enable_auto_mode
        set_config.assert_called_with()

    def test_dyson_purecool_turn_off(self):
        """Test turn off purecool fan."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.turn_off()
        set_config = device.turn_off
        set_config.assert_called_with()

    def test_dyson_purecool_oscillate_off(self):
        """Test turn off purecool oscillation."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        component.oscillate(False)
        set_config = device.disable_oscillation
        set_config.assert_called_with()

    def test_dyson_purecool_oscillate_on(self):
        """Test turn on purecool oscillation."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        component.oscillate(True)
        set_config = device.enable_oscillation
        set_config.assert_called_with()

    def test_oscillating(self):
        """Test purecool oscillation."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.oscillating

        device = _get_purecool_device_off()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.oscillating

    def test_purecool_dyson_on(self):
        """Test purecool device is on."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.is_on

    def test_purecool_dyson_off(self):
        """Test purecool device is off."""
        device = _get_purecool_device_off()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.is_on

        device = _get_device_with_no_state()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.is_on

    def test_purecool_dyson_speed(self):
        """Test get purecool device speed."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.speed == 1

        device = _get_purecool_device_off()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.speed == 4

        device = _get_device_with_no_state()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.speed is None

        device = _get_purecool_device_auto()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.speed == "AUTO"

    def test_dyson_purecool_get_direction(self):
        """Test get purecool device direction."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.current_direction is None

    def test_dyson_purecool_get_speed_list(self):
        """Test purecool get speeds list."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert len(component.speed_list) == 11

    def test_dyson_purecool_supported_features(self):
        """Test purecool supported features."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.supported_features == 3

    def test_purecool_on_message(self):
        """Test purecool when message is received."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        component.entity_id = "entity_id"
        component.schedule_update_ha_state = mock.Mock()
        component.on_message(MockDysonV2State())
        component.schedule_update_ha_state.assert_called_with()

    def test_dyson_purecool_set_angle(self):
        """Test purecool set angle."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        component.set_angle("90", "180")
        component.set_angle("90", "180")
        set_config = device.enable_oscillation
        set_config.assert_called_with("90", "180")

    def test_purecool_angle(self):
        """Test frontal flow direction."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.angle_low == "0090"
        assert component.angle_high == "0180"

    def test_dyson_purecool_set_flow_direction_front(self):
        """Test purecool set frontal flow direction."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.set_flow_direction_front(True)
        set_config = device.enable_frontal_direction
        set_config.assert_called_with()

        component.set_flow_direction_front(False)
        set_config = device.disable_frontal_direction
        set_config.assert_called_with()

    def test_purecool_flow_direction_front(self):
        """Test frontal flow direction."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.flow_direction_front

        device = _get_purecool_device_off()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.flow_direction_front

    def test_dyson_purecool_set_timer(self):
        """Test purecool set timer."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert not component.should_poll
        component.set_timer(60)
        set_config = device.enable_sleep_timer
        set_config.assert_called_with(60)

        component.set_timer(0)
        set_config = device.disable_sleep_timer
        set_config.assert_called_with()

    def test_timer(self):
        """Test purecool timer."""
        device = _get_purecool_device_on()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.timer == 60

        device = _get_purecool_device_off()
        component = dyson.DysonPureCoolDevice(self.hass, device)
        assert component.timer == "OFF"

    def test_purecool_service_set_angle(self):
        """Test set purecool angle service."""
        dyson_device = mock.MagicMock()
        self.hass.data[DYSON_DEVICES] = []
        dyson_device.entity_id = 'fan.living_room'
        self.hass.data[dyson.DYSON_FAN_DEVICES] = [dyson_device]
        dyson.setup_platform(self.hass, None, mock.MagicMock())

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_ANGLE,
                                {"entity_id": "fan.bed_room",
                                 "angle_low": 90,
                                 "angle_high": 180}, True)
        assert not dyson_device.set_angle.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_ANGLE,
                                {"entity_id": "fan.living_room",
                                 "angle_low": 90,
                                 "angle_high": 180}, True)
        assert not dyson_device.set_angle.assert_called_with(90, 180)

    def test_purecool_service_set_flow_direction_front(self):
        """Test set purecool flow direction front service."""
        dyson_device = mock.MagicMock()
        self.hass.data[DYSON_DEVICES] = []
        dyson_device.entity_id = 'fan.living_room'
        self.hass.data[dyson.DYSON_FAN_DEVICES] = [dyson_device]
        dyson.setup_platform(self.hass, None, mock.MagicMock())

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_FLOW_DIRECTION_FRONT,
                                {"entity_id": "fan.bed_room",
                                 "flow_direction_front": True}, True)
        assert not dyson_device.set_flow_direction_front.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_FLOW_DIRECTION_FRONT,
                                {"entity_id": "fan.living_room",
                                 "flow_direction_front": True}, True)
        dyson_device.set_flow_direction_front.assert_called_with(True)

    def test_purecool_service_set_timer(self):
        """Test set purecool timer service."""
        dyson_device = mock.MagicMock()
        self.hass.data[DYSON_DEVICES] = []
        dyson_device.entity_id = 'fan.living_room'
        self.hass.data[dyson.DYSON_FAN_DEVICES] = [dyson_device]
        dyson.setup_platform(self.hass, None, mock.MagicMock())

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_TIMER,
                                {"entity_id": "fan.bed_room",
                                 "timer": 60}, True)
        assert not dyson_device.set_timer.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_TIMER,
                                {"entity_id": "fan.living_room",
                                 "timer": 60}, True)
        assert not dyson_device.set_timer.assert_called_with(60)
