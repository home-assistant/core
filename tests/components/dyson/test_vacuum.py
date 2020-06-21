"""Test the Dyson 360 eye robot vacuum component."""
import unittest
from unittest import mock

from libpurecool.const import Dyson360EyeMode, PowerMode
from libpurecool.dyson_360_eye import Dyson360Eye

from homeassistant.components.dyson import vacuum as dyson
from homeassistant.components.dyson.vacuum import Dyson360EyeDevice

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
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_with_no_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_entities = mock.MagicMock()
        dyson.setup_platform(self.hass, {}, add_entities)
        add_entities.assert_called_with([])

    def test_setup_component(self):
        """Test setup component with devices."""

        def _add_device(devices):
            assert len(devices) == 1
            assert devices[0].name == "Device_Vacuum"

        device_vacuum = _get_vacuum_device_cleaning()
        device_non_vacuum = _get_non_vacuum_device()
        self.hass.data[dyson.DYSON_DEVICES] = [device_vacuum, device_non_vacuum]
        dyson.setup_platform(self.hass, {}, _add_device)

    def test_on_message(self):
        """Test when message is received."""
        device = _get_vacuum_device_cleaning()
        component = Dyson360EyeDevice(device)
        component.entity_id = "entity_id"
        component.schedule_update_ha_state = mock.Mock()
        component.on_message(mock.Mock())
        assert component.schedule_update_ha_state.called

    def test_should_poll(self):
        """Test polling is disable."""
        device = _get_vacuum_device_cleaning()
        component = Dyson360EyeDevice(device)
        assert not component.should_poll

    def test_properties(self):
        """Test component properties."""
        device1 = _get_vacuum_device_cleaning()
        device2 = _get_vacuum_device_unknown_state()
        device3 = _get_vacuum_device_charging()
        component = Dyson360EyeDevice(device1)
        component2 = Dyson360EyeDevice(device2)
        component3 = Dyson360EyeDevice(device3)
        assert component.name == "Device_Vacuum"
        assert component.is_on
        assert component.status == "Cleaning"
        assert component2.status == "Unknown"
        assert component.battery_level == 85
        assert component.fan_speed == "Quiet"
        assert component.fan_speed_list == ["Quiet", "Max"]
        assert component.device_state_attributes["position"] == "(0, 0)"
        assert component.available
        assert component.supported_features == 255
        assert component.battery_icon == "mdi:battery-80"
        assert component3.battery_icon == "mdi:battery-charging-40"

    def test_turn_on(self):
        """Test turn on vacuum."""
        device1 = _get_vacuum_device_charging()
        component1 = Dyson360EyeDevice(device1)
        component1.turn_on()
        assert device1.start.called

        device2 = _get_vacuum_device_pause()
        component2 = Dyson360EyeDevice(device2)
        component2.turn_on()
        assert device2.resume.called

    def test_turn_off(self):
        """Test turn off vacuum."""
        device1 = _get_vacuum_device_cleaning()
        component1 = Dyson360EyeDevice(device1)
        component1.turn_off()
        assert device1.pause.called

    def test_stop(self):
        """Test stop vacuum."""
        device1 = _get_vacuum_device_cleaning()
        component1 = Dyson360EyeDevice(device1)
        component1.stop()
        assert device1.pause.called

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
        assert device1.start.called

        device2 = _get_vacuum_device_pause()
        component2 = Dyson360EyeDevice(device2)
        component2.start_pause()
        assert device2.resume.called

        device3 = _get_vacuum_device_cleaning()
        component3 = Dyson360EyeDevice(device3)
        component3.start_pause()
        assert device3.pause.called

    def test_return_to_base(self):
        """Test return to base."""
        device = _get_vacuum_device_pause()
        component = Dyson360EyeDevice(device)
        component.return_to_base()
        assert device.abort.called
