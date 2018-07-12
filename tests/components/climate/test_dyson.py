"""Test the Dyson fan component."""
import unittest
from unittest import mock

from libpurecoollink.const import (FocusMode, HeatMode, HeatState, HeatTarget,
                                   TiltState)
from libpurecoollink.dyson_pure_state import DysonPureHotCoolState
from libpurecoollink.dyson_pure_hotcool_link import DysonPureHotCoolLink
from homeassistant.components.climate import dyson
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from tests.common import get_test_home_assistant


class MockDysonState(DysonPureHotCoolState):
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
    device.environmental_state = mock.Mock()
    return device


def _get_device_focus():
    """Return a device with fan state of focus mode."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state.focus_mode = FocusMode.FOCUS_ON.value
    return device


def _get_device_diffuse():
    """Return a device with fan state of diffuse mode."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    return device


def _get_device_cool():
    """Return a device with state of cooling."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state.tilt = TiltState.TILT_FALSE.value
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    device.state.heat_target = HeatTarget.celsius(12)
    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    device.environmental_state.temperature = 288
    device.environmental_state.humidity = 53
    return device


def _get_device_heat_off():
    """Return a device with state of heat reached target."""
    device = mock.Mock()
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.tilt = TiltState.TILT_FALSE.value
    device.state.focus_mode = FocusMode.FOCUS_ON.value
    device.state.heat_target = HeatTarget.celsius(20)
    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    device.environmental_state.temperature = 293
    device.environmental_state.humidity = 53
    return device


def _get_device_heat_on():
    """Return a device with state of heating."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    device.name = "Device_name"
    device.state = mock.Mock()
    device.state.tilt = TiltState.TILT_FALSE.value
    device.state.focus_mode = FocusMode.FOCUS_ON.value
    device.state.heat_target = HeatTarget.celsius(23)
    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_ON.value
    device.environmental_state.temperature = 289
    device.environmental_state.humidity = 53
    return device


class DysonTest(unittest.TestCase):
    """Dyson Climate component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_without_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_devices = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_devices)
        self.assertFalse(add_devices.called)

    def test_setup_component(self):
        """Test setup component with devices."""
        device_fan = _get_device_heat_on()
        device_non_fan = _get_device_off()

        def _add_device(devices):
            assert len(devices) == 1
            assert devices[0].name == "Device_name"

        self.hass.data[dyson.DYSON_DEVICES] = [device_fan, device_non_fan]
        dyson.setup_platform(self.hass, None, _add_device)

    def test_dyson_set_temperature(self):
        """Test set climate temperature."""
        device = _get_device_heat_on()
        device.temp_unit = TEMP_CELSIUS
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertFalse(entity.should_poll)

        def celsius_to_kelvin_str(celsius):
            """Convert celssius to kelvin in string format."""
            return str((celsius + 273) * 10)

        kwargs = {ATTR_TEMPERATURE: 23}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_target=celsius_to_kelvin_str(23))

        # Should clip the target temperature between 1 and 37 inclusive.
        kwargs = {ATTR_TEMPERATURE: 50}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_target=celsius_to_kelvin_str(37))

        kwargs = {ATTR_TEMPERATURE: -5}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_target=celsius_to_kelvin_str(1))

    def test_dyson_set_fan_mode(self):
        """Test set fan mode."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertFalse(entity.should_poll)

        entity.set_fan_mode(dyson.STATE_FOCUS)
        set_config = device.set_configuration
        set_config.assert_called_with(focus_mode=FocusMode.FOCUS_ON)

        entity.set_fan_mode(dyson.STATE_DIFFUSE)
        set_config = device.set_configuration
        set_config.assert_called_with(focus_mode=FocusMode.FOCUS_OFF)

    def test_dyson_fan_list(self):
        """Test get fan list."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(len(entity.fan_list), 2)
        self.assertTrue(dyson.STATE_FOCUS in entity.fan_list)
        self.assertTrue(dyson.STATE_DIFFUSE in entity.fan_list)

    def test_dyson_fan_mode_focus(self):
        """Test fan focus mode."""
        device = _get_device_focus()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(entity.current_fan_mode, dyson.STATE_FOCUS)

    def test_dyson_fan_mode_diffuse(self):
        """Test fan diffuse mode."""
        device = _get_device_diffuse()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(entity.current_fan_mode, dyson.STATE_DIFFUSE)

    def test_dyson_set_operation_mode(self):
        """Test set operation mode."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertFalse(entity.should_poll)

        entity.set_operation_mode(dyson.STATE_HEAT)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_ON)

        entity.set_operation_mode(dyson.STATE_COOL)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_OFF)

    def test_dyson_operation_list(self):
        """Test get operation list."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(len(entity.operation_list), 2)
        self.assertTrue(dyson.STATE_HEAT in entity.operation_list)
        self.assertTrue(dyson.STATE_COOL in entity.operation_list)

    def test_dyson_heat_off(self):
        """Test turn off heat."""
        device = _get_device_heat_off()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.set_operation_mode(dyson.STATE_COOL)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_OFF)

    def test_dyson_heat_on(self):
        """Test turn on heat."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.set_operation_mode(dyson.STATE_HEAT)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_ON)

    def test_dyson_heat_value_on(self):
        """Test get heat value on."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(entity.current_operation, dyson.STATE_HEAT)

    def test_dyson_heat_value_off(self):
        """Test get heat value off."""
        device = _get_device_cool()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(entity.current_operation, dyson.STATE_COOL)

    def test_dyson_heat_value_idle(self):
        """Test get heat value idle."""
        device = _get_device_heat_off()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        self.assertEqual(entity.current_operation, dyson.STATE_IDLE)

    def test_on_message(self):
        """Test when message is received."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.schedule_update_ha_state = mock.Mock()
        entity.on_message(MockDysonState())
        entity.schedule_update_ha_state.assert_called_with()
