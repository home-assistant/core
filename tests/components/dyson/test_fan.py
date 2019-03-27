"""Test the Dyson fan component."""
import unittest
from unittest import mock

from homeassistant.setup import setup_component
from homeassistant.components import dyson as dyson_parent
from homeassistant.components.dyson import DYSON_DEVICES, fan as dyson
from homeassistant.components.fan import (ATTR_SPEED, ATTR_SPEED_LIST,
                                          ATTR_OSCILLATING)
from tests.common import get_test_home_assistant
from libpurecoollink.const import FanSpeed, FanMode, NightMode, Oscillation
from libpurecoollink.dyson_pure_state import DysonPureCoolState
from libpurecoollink.dyson_pure_cool_link import DysonPureCoolLink


class MockDysonState(DysonPureCoolState):
    """Mock Dyson state."""

    def __init__(self):
        """Create new Mock Dyson State."""
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
            assert len(devices) == 1
            assert devices[0].name == "Device_name"

        device_fan = _get_device_on()
        device_non_fan = _get_device_off()

        self.hass.data[dyson.DYSON_DEVICES] = [device_fan, device_non_fan]
        dyson.setup_platform(self.hass, None, _add_device)

    @mock.patch('libpurecoollink.dyson.DysonAccount.devices',
                return_value=[_get_device_on()])
    @mock.patch('libpurecoollink.dyson.DysonAccount.login', return_value=True)
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

        assert dyson.ATTR_IS_NIGHT_MODE in state.attributes
        assert dyson.ATTR_IS_AUTO_MODE in state.attributes
        assert ATTR_SPEED in state.attributes
        assert ATTR_SPEED_LIST in state.attributes
        assert ATTR_OSCILLATING in state.attributes

    @mock.patch('libpurecoollink.dyson.DysonAccount.devices',
                return_value=[_get_device_on()])
    @mock.patch('libpurecoollink.dyson.DysonAccount.login', return_value=True)
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
        component.night_mode(True)
        set_config = device.set_configuration
        set_config.assert_called_with(night_mode=NightMode.NIGHT_MODE_ON)

        component.night_mode(False)
        set_config = device.set_configuration
        set_config.assert_called_with(night_mode=NightMode.NIGHT_MODE_OFF)

    def test_is_night_mode(self):
        """Test night mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.is_night_mode

        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.is_night_mode

    def test_dyson_turn_auto_mode(self):
        """Test turn on/off fan with auto mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.should_poll
        component.auto_mode(True)
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.AUTO)

        component.auto_mode(False)
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN)

    def test_is_auto_mode(self):
        """Test auto mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert not component.is_auto_mode

        device = _get_device_auto()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        assert component.is_auto_mode

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
        assert not dyson_device.night_mode.called

        self.hass.services.call(dyson.DOMAIN, dyson.SERVICE_SET_NIGHT_MODE,
                                {"entity_id": "fan.living_room",
                                 "night_mode": True}, True)
        dyson_device.night_mode.assert_called_with(True)
