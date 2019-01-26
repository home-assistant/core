"""Test the Dyson fan component."""
import unittest
from unittest import mock

from libpurecool.const import FanSpeed, FanMode, NightMode, Oscillation
from libpurecool.dyson import DysonAccount
from libpurecool.dyson_pure_cool import DysonPureCool
from libpurecool.dyson_pure_cool_link import DysonPureCoolLink
from libpurecool.dyson_pure_state import DysonPureCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureCoolV2State

from homeassistant.components import dyson as dyson_parent
from homeassistant.components.dyson import DYSON_DEVICES
from homeassistant.components.fan import (dyson, ATTR_SPEED, ATTR_SPEED_LIST,
                                          ATTR_OSCILLATING, SPEED_LOW,
                                          SPEED_MEDIUM, SPEED_HIGH)
from homeassistant.setup import setup_component
from tests.common import get_test_home_assistant


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


def _get_dyson_purecool_device():
    """Return a valid device provide by Dyson web services."""
    device = mock.Mock(spec=DysonPureCool)
    device.serial = "XX-XXXXX-XX"
    device.name = "Device_name"
    device.connect = mock.Mock(return_value=True)
    device.auto_connect = mock.Mock(return_value=True)
    device.state = mock.Mock()
    device.state.oscillation = "OION"
    device.state.fan_power = "ON"
    device.state.speed = FanSpeed.FAN_SPEED_AUTO.value
    device.state.night_mode = "OFF"
    device.state.auto_mode = "ON"
    device.state.oscillation_angle_low = "0090"
    device.state.oscillation_angle_high = "0180"
    device.state.front_direction = "ON"
    device.state.sleep_timer = "OFF"
    return device


def _get_config():
    """Return a config dictionary."""
    return {dyson_parent.DOMAIN: {
        dyson_parent.CONF_USERNAME: "email",
        dyson_parent.CONF_PASSWORD: "password",
        dyson_parent.CONF_LANGUAGE: "GB",
        dyson_parent.CONF_DEVICES: [
            {
                "device_id": "XX-XXXXX-XX",
                "device_ip": "192.168.0.1"
            }
        ]
    }}


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


class DysonSetupTest(unittest.TestCase):
    """Dyson component setup tests."""

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
        device_purecool_fan = _get_dyson_purecool_device()
        device_non_fan = _get_device_off()

        self.hass.data[dyson.DYSON_DEVICES] = [device_fan,
                                               device_purecool_fan,
                                               device_non_fan]
        dyson.setup_platform(self.hass, None, _add_device)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_purecool_service_set_night_mode(self,
                                             mocked_login, mocked_devices):
        """Test set night mode service."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.entity_id = 'fan.living_room'
        fan.set_night_mode = mock.MagicMock()

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_NIGHT_MODE,
                                {"entity_id": "fan.bed_room",
                                 "night_mode": True}, True)
        assert not fan.set_night_mode.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_NIGHT_MODE,
                                {"entity_id": "fan.living_room",
                                 "night_mode": True}, True)
        fan.set_night_mode.assert_called_with(True)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_purecool_service_set_auto_mode(self,
                                            mocked_login, mocked_devices):
        """Test set auto mode service."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.entity_id = 'fan.living_room'
        fan.set_auto_mode = mock.MagicMock()

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_AUTO_MODE,
                                {"entity_id": "fan.bed_room",
                                 "auto_mode": True}, True)
        assert not fan.set_auto_mode.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_AUTO_MODE,
                                {"entity_id": "fan.living_room",
                                 "auto_mode": True}, True)
        fan.set_auto_mode.assert_called_with(True)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_purecool_service_set_angle(self, mocked_login, mocked_devices):
        """Test set purecool angle service."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.entity_id = 'fan.living_room'
        fan.set_angle = mock.MagicMock()

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_ANGLE,
                                {"entity_id": "fan.bed_room",
                                 "angle_low": 90,
                                 "angle_high": 180}, True)
        assert not fan.set_angle.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_ANGLE,
                                {"entity_id": "fan.living_room",
                                 "angle_low": 90,
                                 "angle_high": 180}, True)
        assert not fan.set_angle.assert_called_with(90, 180)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_purecool_service_set_flow_direction_front(self,
                                                       mocked_login,
                                                       mocked_devices):
        """Test set purecool flow direction front service."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.entity_id = 'fan.living_room'
        fan.set_flow_direction_front = mock.MagicMock()

        self.hass.services.call(dyson.DOMAIN,
                                dyson.SERVICE_SET_FLOW_DIRECTION_FRONT,
                                {"entity_id": "fan.bed_room",
                                 "flow_direction_front": True}, True)
        assert not fan.set_flow_direction_front.called

        self.hass.services.call(dyson.DOMAIN,
                                dyson.SERVICE_SET_FLOW_DIRECTION_FRONT,
                                {"entity_id": "fan.living_room",
                                 "flow_direction_front": True}, True)
        fan.set_flow_direction_front.assert_called_with(True)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_purecool_service_set_timer(self, mocked_login, mocked_devices):
        """Test set purecool timer service."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.entity_id = 'fan.living_room'
        fan.set_timer = mock.MagicMock()

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_TIMER,
                                {"entity_id": "fan.bed_room",
                                 "timer": 60}, True)
        assert not fan.set_timer.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_TIMER,
                                {"entity_id": "fan.living_room",
                                 "timer": 60}, True)
        assert not fan.set_timer.assert_called_with(60)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_purecool_service_set_dyson_speed(self,
                                              mocked_login, mocked_devices):
        """Test set purecool exact speed service."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.entity_id = 'fan.living_room'
        fan.set_dyson_speed = mock.MagicMock()

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_DYSON_SPEED,
                                {"entity_id": "fan.bed_room",
                                 "dyson_speed": 1}, True)
        assert not fan.set_dyson_speed.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_DYSON_SPEED,
                                {"entity_id": "fan.living_room",
                                 "dyson_speed": 1}, True)
        assert not fan.set_dyson_speed.assert_called_with(1)


class DysonTest(unittest.TestCase):
    """Dyson fan component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

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


class DysonPurecoolTest(unittest.TestCase):
    """Dyson purecool fan component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_empty_state(self, mocked_login):
        """Test purecool fan with no status."""
        test_device = _get_dyson_purecool_device()
        test_device.state = None
        with mock.patch.object(DysonAccount, 'devices',
                               return_value=[test_device]):
            dyson_parent.setup(self.hass, _get_config())
            self.hass.block_till_done()
            device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
            assert device.is_on is False
            assert device.speed is None
            assert device.dyson_speed is None
            assert device.should_poll is False

    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
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

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_on_message(self, mocked_login, mocked_devices):
        """Test on message for purecool fan."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.schedule_update_ha_state = mock.Mock()
        fan.on_message(MockDysonV2State())
        fan.schedule_update_ha_state.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_turn_on(self, mocked_login, mocked_devices):
        """Test turn on purecool fan."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.turn_on()
        fan._device.turn_on.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_turn_on_with_speed(self, mocked_login, mocked_devices):
        """Test turn on purecool fan with speed."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.turn_on(SPEED_LOW)
        fan._device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_4)
        fan.turn_on(SPEED_MEDIUM)
        fan._device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_7)
        fan.turn_on(SPEED_HIGH)
        fan._device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_10)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_turn_off(self, mocked_login, mocked_devices):
        """Test turn off purecool fan."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.turn_off()
        fan._device.turn_off.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_set_dyson_speed(self, mocked_login, mocked_devices):
        """Test set exact speed for purecool fan."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.set_dyson_speed(4)
        fan._device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_4)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_oscillate(self, mocked_login, mocked_devices):
        """Test set purecool fan oscillation."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.oscillate(True)
        fan._device.enable_oscillation.assert_called_with()
        fan.oscillate(False)
        fan._device.disable_oscillation.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_set_night_mode(self, mocked_login, mocked_devices):
        """Test set fan night mode."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.set_night_mode(True)
        fan._device.enable_night_mode.assert_called_with()
        fan.set_night_mode(False)
        fan._device.disable_night_mode.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_set_auto_mode(self, mocked_login, mocked_devices):
        """Test set fan auto mode."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.set_auto_mode(True)
        fan._device.enable_auto_mode.assert_called_with()
        fan.set_auto_mode(False)
        fan._device.disable_auto_mode.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_set_angle(self, mocked_login, mocked_devices):
        """Test set fan set angle."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.set_angle(10, 50)
        fan._device.enable_oscillation.assert_called_with(10, 50)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_flow_direction_front(self, mocked_login, mocked_devices):
        """Test set fan frontal flow direction."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.set_flow_direction_front(True)
        fan._device.enable_frontal_direction.assert_called_with()
        fan.set_flow_direction_front(False)
        fan._device.disable_frontal_direction.assert_called_with()

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_set_sleep_timer(self, mocked_login, mocked_devices):
        """Test set fan sleep timer."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        fan = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        fan.set_timer(0)
        fan._device.disable_sleep_timer.assert_called_with()
        fan.set_timer(50)
        fan._device.enable_sleep_timer.assert_called_with(50)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_oscillating(self, mocked_login, mocked_devices):
        """Test purecool oscillation."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.oscillating is True

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_is_on(self, mocked_login, mocked_devices):
        """Test purecool power status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.is_on is True

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_speed_auto(self, mocked_login, mocked_devices):
        """Test purecool auto speed status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.speed is SPEED_MEDIUM

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_speed_low(self, mocked_login):
        """Test purecool low speed status."""
        test_device = _get_dyson_purecool_device()
        test_device.state.speed = FanSpeed.FAN_SPEED_4.value
        with mock.patch.object(DysonAccount, 'devices',
                               return_value=[test_device]):
            dyson_parent.setup(self.hass, _get_config())
            self.hass.block_till_done()
            device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
            assert device.speed is SPEED_LOW

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_speed_medium(self, mocked_login):
        """Test purecool medium speed status."""
        test_device = _get_dyson_purecool_device()
        test_device.state.speed = FanSpeed.FAN_SPEED_7.value
        with mock.patch.object(DysonAccount, 'devices',
                               return_value=[test_device]):
            dyson_parent.setup(self.hass, _get_config())
            self.hass.block_till_done()
            device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
            assert device.speed is SPEED_MEDIUM

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_speed_high(self, mocked_login):
        """Test purecool high speed status."""
        test_device = _get_dyson_purecool_device()
        test_device.state.speed = FanSpeed.FAN_SPEED_10.value
        with mock.patch.object(DysonAccount, 'devices',
                               return_value=[test_device]):
            dyson_parent.setup(self.hass, _get_config())
            self.hass.block_till_done()
            device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
            assert device.speed is SPEED_HIGH

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_dyson_speed_auto(self, mocked_login, mocked_devices):
        """Test purecool dyson auto speed status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.dyson_speed is FanSpeed.FAN_SPEED_AUTO.value

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    def test_dyson_speed(self, mocked_login):
        """Test purecool dyson speed status."""
        test_device = _get_dyson_purecool_device()
        test_device.state.speed = FanSpeed.FAN_SPEED_10.value
        with mock.patch.object(DysonAccount, 'devices',
                               return_value=[test_device]):
            dyson_parent.setup(self.hass, _get_config())
            self.hass.block_till_done()
            device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
            assert device.dyson_speed is int(FanSpeed.FAN_SPEED_10.value)

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_night_mode(self, mocked_login, mocked_devices):
        """Test purecool night mode status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.night_mode is False

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_auto_mode(self, mocked_login, mocked_devices):
        """Test purecool auto mode status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.auto_mode is True

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_angles(self, mocked_login, mocked_devices):
        """Test purecool angle states."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()

        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]

        assert device.angle_low == "0090"
        assert device.angle_high == "0180"

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_frontal_flow_direction(self, mocked_login, mocked_devices):
        """Test purecool frontal flow direction status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.flow_direction_front is True

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_timer(self, mocked_login, mocked_devices):
        """Test purecool timer status."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.timer == "OFF"

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_speed_list(self, mocked_login, mocked_devices):
        """Test purecool speed list."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.speed_list == [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_dyson_speed_list(self, mocked_login, mocked_devices):
        """Test purecool dyson speed list."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert len(device.dyson_speed_list) == 10

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_dyson_supported_features(self, mocked_login, mocked_devices):
        """Test purecool supported features."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        device = self.hass.data[dyson.DYSON_FAN_DEVICES][0]
        assert device.supported_features == 3

    @mock.patch('libpurecool.dyson.DysonAccount.login', return_value=True)
    @mock.patch('libpurecool.dyson.DysonAccount.devices',
                return_value=[_get_dyson_purecool_device()])
    def test_dyson_device_state_attributes(self,
                                           mocked_devices, mocked_login):
        """Test purecool device state attributes list."""
        dyson_parent.setup(self.hass, _get_config())
        self.hass.block_till_done()
        state = self.hass.states.get("{}.{}".format(
            dyson.DOMAIN,
            mocked_devices.return_value[0].name))

        assert dyson.ATTR_NIGHT_MODE in state.attributes
        assert dyson.ATTR_AUTO_MODE in state.attributes
        assert dyson.ATTR_ANGLE_LOW in state.attributes
        assert dyson.ATTR_ANGLE_HIGH in state.attributes
        assert dyson.ATTR_FLOW_DIRECTION_FRONT in state.attributes
        assert dyson.ATTR_TIMER in state.attributes
        assert ATTR_SPEED in state.attributes
        assert ATTR_SPEED_LIST in state.attributes
        assert ATTR_OSCILLATING in state.attributes
