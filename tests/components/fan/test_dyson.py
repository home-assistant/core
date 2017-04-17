"""Test the Dyson fan component."""
import unittest
from unittest import mock

from homeassistant.components.fan import dyson
from tests.common import get_test_home_assistant
from libpurecoollink.const import FanSpeed, FanMode, NightMode, Oscillation


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
    return device


def _get_device_on():
    """Return a valid state on."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.fan_mode = "FAN"
    device.state.oscillation = "ON"
    device.state.speed = "0001"
    return device


class DysonTest(unittest.TestCase):
    """Dyson Sensor component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_with_no_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_devices = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_devices)
        add_devices.assert_called_with([])

    def test_setup_component(self):
        """Test setup component with devices."""
        def _add_device(devices):
            assert len(devices) == 1
            assert devices[0].name == "Device_name"

        device = _get_device_on()
        self.hass.data[dyson.DYSON_DEVICES] = [device]
        dyson.setup_platform(self.hass, None, _add_device)

    def test_dyson_set_speed(self):
        """Test set fan speed."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.should_poll)
        component.set_speed("0001")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN,
                                      fan_speed=FanSpeed.FAN_SPEED_1,
                                      night_mode=NightMode.NIGHT_MODE_OFF)

    def test_dyson_turn_on(self):
        """Test turn on fan."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.should_poll)
        component.turn_on()
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN)

    def test_dyson_turn_on_night_mode(self):
        """Test turn on fan with night mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.should_poll)
        component.turn_on("NIGHT_MODE")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.AUTO,
                                      night_mode=NightMode.NIGHT_MODE_ON)

    def test_dyson_turn_on_auto_mode(self):
        """Test turn on fan with auto mode."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.should_poll)
        component.turn_on("AUTO")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.AUTO,
                                      night_mode=NightMode.NIGHT_MODE_OFF)

    def test_dyson_turn_on_speed(self):
        """Test turn on fan with specified speed."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.should_poll)
        component.turn_on("0001")
        set_config = device.set_configuration
        set_config.assert_called_with(fan_mode=FanMode.FAN,
                                      fan_speed=FanSpeed.FAN_SPEED_1,
                                      night_mode=NightMode.NIGHT_MODE_OFF)

    def test_dyson_turn_off(self):
        """Test turn off fan."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.should_poll)
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
        self.assertTrue(component.oscillating)

    def test_dyson_oscillate_value_off(self):
        """Test get oscillation value off."""
        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.oscillating)

    def test_dyson_on(self):
        """Test device is on."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertTrue(component.is_on)

    def test_dyson_off(self):
        """Test device is off."""
        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.is_on)

        device = _get_device_with_no_state()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertFalse(component.is_on)

    def test_dyson_get_speed(self):
        """Test get device speed."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertEqual(component.speed, "0001")

        device = _get_device_off()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertEqual(component.speed, "NIGHT_MODE")

        device = _get_device_with_no_state()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertIsNone(component.speed)

    def test_dyson_get_direction(self):
        """Test get device direction."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertIsNone(component.current_direction)

    def test_dyson_get_speed_list(self):
        """Test get speeds list."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertEqual(len(component.speed_list), 12)

    def test_dyson_supported_features(self):
        """Test supported features."""
        device = _get_device_on()
        component = dyson.DysonPureCoolLinkDevice(self.hass, device)
        self.assertEqual(component.supported_features, 3)
