"""Test the Dyson 360 eye robot vacuum component."""
import unittest
from unittest import mock

from libpurecoollink.dyson_360_eye import Dyson360Eye
from libpurecoollink.const import Dyson360EyeMode, PowerMode

from homeassistant.components.vacuum import dyson
from homeassistant.components.vacuum.dyson import Dyson360EyeDevice
from tests.common import get_test_home_assistant


def _get_non_vacuum_device():
    """Return a non vacuum device."""
    device = mock.Mock()
    device.name = "Device_Fan"
    device.state = None
    return device


def _get_vacuum_device_cleaning():
    """Return a vacuum device running."""
    device = mock.Mock(spec=Dyson360Eye)
    device.name = "Device_Vacuum"
    device.state = mock.MagicMock()
    device.state.state = Dyson360EyeMode.FULL_CLEAN_RUNNING
    device.state.battery_level = 85
    device.state.power_mode = PowerMode.QUIET
    device.state.position = (0, 0)
    return device


def _get_vacuum_device_charging():
    """Return a vacuum device charging."""
    device = mock.Mock(spec=Dyson360Eye)
    device.name = "Device_Vacuum"
    device.state = mock.MagicMock()
    device.state.state = Dyson360EyeMode.INACTIVE_CHARGING
    device.state.battery_level = 40
    device.state.power_mode = PowerMode.QUIET
    device.state.position = (0, 0)
    return device


def _get_vacuum_device_pause():
    """Return a vacuum device in pause."""
    device = mock.MagicMock(spec=Dyson360Eye)
    device.name = "Device_Vacuum"
    device.state = mock.MagicMock()
    device.state.state = Dyson360EyeMode.FULL_CLEAN_PAUSED
    device.state.battery_level = 40
    device.state.power_mode = PowerMode.QUIET
    device.state.position = (0, 0)
    return device


def _get_vacuum_device_unknown_state():
    """Return a vacuum device with unknown state."""
    device = mock.Mock(spec=Dyson360Eye)
    device.name = "Device_Vacuum"
    device.state = mock.MagicMock()
    device.state.state = "Unknown"
    return device


class DysonTest(unittest.TestCase):
    """Dyson 360 eye robot vacuum component test class."""

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
        dyson.setup_platform(self.hass, {}, add_devices)
        add_devices.assert_called_with([])

    def test_setup_component(self):
        """Test setup component with devices."""
        def _add_device(devices):
            assert len(devices) == 1
            assert devices[0].name == "Device_Vacuum"

        device_vacuum = _get_vacuum_device_cleaning()
        device_non_vacuum = _get_non_vacuum_device()
        self.hass.data[dyson.DYSON_DEVICES] = [device_vacuum,
                                               device_non_vacuum]
        dyson.setup_platform(self.hass, {}, _add_device)

    def test_on_message(self):
        """Test when message is received."""
        device = _get_vacuum_device_cleaning()
        component = Dyson360EyeDevice(device)
        component.entity_id = "entity_id"
        component.schedule_update_ha_state = mock.Mock()
        component.on_message(mock.Mock())
        self.assertTrue(component.schedule_update_ha_state.called)

    def test_should_poll(self):
        """Test polling is disable."""
        device = _get_vacuum_device_cleaning()
        component = Dyson360EyeDevice(device)
        self.assertFalse(component.should_poll)

    def test_properties(self):
        """Test component properties."""
        device1 = _get_vacuum_device_cleaning()
        device2 = _get_vacuum_device_unknown_state()
        device3 = _get_vacuum_device_charging()
        component = Dyson360EyeDevice(device1)
        component2 = Dyson360EyeDevice(device2)
        component3 = Dyson360EyeDevice(device3)
        self.assertEqual(component.name, "Device_Vacuum")
        self.assertTrue(component.is_on)
        self.assertEqual(component.status, "Cleaning")
        self.assertEqual(component2.status, "Unknown")
        self.assertEqual(component.battery_level, 85)
        self.assertEqual(component.fan_speed, "Quiet")
        self.assertEqual(component.fan_speed_list, ["Quiet", "Max"])
        self.assertEqual(component.device_state_attributes['position'],
                         '(0, 0)')
        self.assertTrue(component.available)
        self.assertEqual(component.supported_features, 255)
        self.assertEqual(component.battery_icon, "mdi:battery-80")
        self.assertEqual(component3.battery_icon, "mdi:battery-charging-40")

    def test_turn_on(self):
        """Test turn on vacuum."""
        device1 = _get_vacuum_device_charging()
        component1 = Dyson360EyeDevice(device1)
        component1.turn_on()
        self.assertTrue(device1.start.called)

        device2 = _get_vacuum_device_pause()
        component2 = Dyson360EyeDevice(device2)
        component2.turn_on()
        self.assertTrue(device2.resume.called)

    def test_turn_off(self):
        """Test turn off vacuum."""
        device1 = _get_vacuum_device_cleaning()
        component1 = Dyson360EyeDevice(device1)
        component1.turn_off()
        self.assertTrue(device1.pause.called)

    def test_stop(self):
        """Test stop vacuum."""
        device1 = _get_vacuum_device_cleaning()
        component1 = Dyson360EyeDevice(device1)
        component1.stop()
        self.assertTrue(device1.pause.called)

    def test_set_fan_speed(self):
        """Test set fan speed vacuum."""
        device1 = _get_vacuum_device_cleaning()
        component1 = Dyson360EyeDevice(device1)
        component1.set_fan_speed("Max")
        device1.set_power_mode.assert_called_with(PowerMode.MAX)

    def test_start_pause(self):
        """Test start/pause."""
        device1 = _get_vacuum_device_charging()
        component1 = Dyson360EyeDevice(device1)
        component1.start_pause()
        self.assertTrue(device1.start.called)

        device2 = _get_vacuum_device_pause()
        component2 = Dyson360EyeDevice(device2)
        component2.start_pause()
        self.assertTrue(device2.resume.called)

        device3 = _get_vacuum_device_cleaning()
        component3 = Dyson360EyeDevice(device3)
        component3.start_pause()
        self.assertTrue(device3.pause.called)

    def test_return_to_base(self):
        """Test return to base."""
        device = _get_vacuum_device_pause()
        component = Dyson360EyeDevice(device)
        component.return_to_base()
        self.assertTrue(device.abort.called)
