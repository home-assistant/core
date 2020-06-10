"""Test the Dyson fan component."""
import unittest
from unittest import mock

from libpurecool.const import FocusMode, HeatMode, HeatState, HeatTarget
from libpurecool.dyson_pure_hotcool_link import DysonPureHotCoolLink
from libpurecool.dyson_pure_state import DysonPureHotCoolState

from homeassistant.components import dyson as dyson_parent
from homeassistant.components.dyson import climate as dyson
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from .common import load_mock_device

from tests.async_mock import patch
from tests.common import get_test_home_assistant


class MockDysonState(DysonPureHotCoolState):
    """Mock Dyson state."""

    def __init__(self):
        """Create new Mock Dyson State."""
        pass


def _get_config():
    """Return a config dictionary."""
    return {
        dyson_parent.DOMAIN: {
            dyson_parent.CONF_USERNAME: "email",
            dyson_parent.CONF_PASSWORD: "password",
            dyson_parent.CONF_LANGUAGE: "GB",
            dyson_parent.CONF_DEVICES: [
                {"device_id": "XX-XXXXX-XX", "device_ip": "192.168.0.1"},
                {"device_id": "YY-YYYYY-YY", "device_ip": "192.168.0.2"},
            ],
        }
    }


def _get_device_with_no_state():
    """Return a device with no state."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state = None
    device.environmental_state = None
    return device


def _get_device_off():
    """Return a device with state off."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    return device


def _get_device_focus():
    """Return a device with fan state of focus mode."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_ON.value
    return device


def _get_device_diffuse():
    """Return a device with fan state of diffuse mode."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    return device


def _get_device_cool():
    """Return a device with state of cooling."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    device.state.heat_target = HeatTarget.celsius(12)
    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    return device


def _get_device_heat_off():
    """Return a device with state of heat reached target."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    return device


def _get_device_heat_on():
    """Return a device with state of heating."""
    device = mock.Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.serial = "YY-YYYYY-YY"
    device.state.heat_target = HeatTarget.celsius(23)
    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_ON.value
    device.environmental_state.temperature = 289
    device.environmental_state.humidity = 53
    return device


class DysonTest(unittest.TestCase):
    """Dyson Climate component test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_without_devices(self):
        """Test setup component with no devices."""
        self.hass.data[dyson.DYSON_DEVICES] = []
        add_devices = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_devices)
        add_devices.assert_not_called()

    def test_setup_component_with_devices(self):
        """Test setup component with valid devices."""
        devices = [
            _get_device_with_no_state(),
            _get_device_off(),
            _get_device_heat_on(),
        ]
        self.hass.data[dyson.DYSON_DEVICES] = devices
        add_devices = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_devices, discovery_info={})
        assert add_devices.called

    def test_setup_component_with_invalid_devices(self):
        """Test setup component with invalid devices."""
        devices = [None, "foo_bar"]
        self.hass.data[dyson.DYSON_DEVICES] = devices
        add_devices = mock.MagicMock()
        dyson.setup_platform(self.hass, None, add_devices, discovery_info={})
        add_devices.assert_called_with([])

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
        assert not entity.should_poll

        # Without target temp.
        kwargs = {}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_not_called()

        kwargs = {ATTR_TEMPERATURE: 23}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(
            heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(23)
        )

        # Should clip the target temperature between 1 and 37 inclusive.
        kwargs = {ATTR_TEMPERATURE: 50}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(
            heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(37)
        )

        kwargs = {ATTR_TEMPERATURE: -5}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(
            heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(1)
        )

    def test_dyson_set_temperature_when_cooling_mode(self):
        """Test set climate temperature when heating is off."""
        device = _get_device_cool()
        device.temp_unit = TEMP_CELSIUS
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.schedule_update_ha_state = mock.Mock()

        kwargs = {ATTR_TEMPERATURE: 23}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(
            heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(23)
        )

    def test_dyson_set_fan_mode(self):
        """Test set fan mode."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert not entity.should_poll

        entity.set_fan_mode(dyson.FAN_FOCUS)
        set_config = device.set_configuration
        set_config.assert_called_with(focus_mode=FocusMode.FOCUS_ON)

        entity.set_fan_mode(dyson.FAN_DIFFUSE)
        set_config = device.set_configuration
        set_config.assert_called_with(focus_mode=FocusMode.FOCUS_OFF)

    def test_dyson_fan_modes(self):
        """Test get fan list."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert len(entity.fan_modes) == 2
        assert dyson.FAN_FOCUS in entity.fan_modes
        assert dyson.FAN_DIFFUSE in entity.fan_modes

    def test_dyson_fan_mode_focus(self):
        """Test fan focus mode."""
        device = _get_device_focus()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.fan_mode == dyson.FAN_FOCUS

    def test_dyson_fan_mode_diffuse(self):
        """Test fan diffuse mode."""
        device = _get_device_diffuse()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.fan_mode == dyson.FAN_DIFFUSE

    def test_dyson_set_hvac_mode(self):
        """Test set operation mode."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert not entity.should_poll

        entity.set_hvac_mode(dyson.HVAC_MODE_HEAT)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_ON)

        entity.set_hvac_mode(dyson.HVAC_MODE_COOL)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_OFF)

    def test_dyson_operation_list(self):
        """Test get operation list."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert len(entity.hvac_modes) == 2
        assert dyson.HVAC_MODE_HEAT in entity.hvac_modes
        assert dyson.HVAC_MODE_COOL in entity.hvac_modes

    def test_dyson_heat_off(self):
        """Test turn off heat."""
        device = _get_device_heat_off()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.set_hvac_mode(dyson.HVAC_MODE_COOL)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_OFF)

    def test_dyson_heat_on(self):
        """Test turn on heat."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.set_hvac_mode(dyson.HVAC_MODE_HEAT)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_ON)

    def test_dyson_heat_value_on(self):
        """Test get heat value on."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.hvac_mode == dyson.HVAC_MODE_HEAT

    def test_dyson_heat_value_off(self):
        """Test get heat value off."""
        device = _get_device_cool()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.hvac_mode == dyson.HVAC_MODE_COOL

    def test_dyson_heat_value_idle(self):
        """Test get heat value idle."""
        device = _get_device_heat_off()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.hvac_mode == dyson.HVAC_MODE_HEAT
        assert entity.hvac_action == dyson.CURRENT_HVAC_IDLE

    def test_on_message(self):
        """Test when message is received."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        entity.schedule_update_ha_state = mock.Mock()
        entity.on_message(MockDysonState())
        entity.schedule_update_ha_state.assert_called_with()

    def test_general_properties(self):
        """Test properties of entity."""
        device = _get_device_with_no_state()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.should_poll is False
        assert entity.supported_features == dyson.SUPPORT_FLAGS
        assert entity.temperature_unit == TEMP_CELSIUS

    def test_property_current_humidity(self):
        """Test properties of current humidity."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.current_humidity == 53

    def test_property_current_humidity_with_invalid_env_state(self):
        """Test properties of current humidity with invalid env state."""
        device = _get_device_off()
        device.environmental_state.humidity = 0
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.current_humidity is None

    def test_property_current_humidity_without_env_state(self):
        """Test properties of current humidity without env state."""
        device = _get_device_with_no_state()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.current_humidity is None

    def test_property_current_temperature(self):
        """Test properties of current temperature."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        # Result should be in celsius, hence then subtraction of 273.
        assert entity.current_temperature == 289 - 273

    def test_property_target_temperature(self):
        """Test properties of target temperature."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkDevice(device)
        assert entity.target_temperature == 23


@patch(
    "libpurecool.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on(), _get_device_cool()],
)
@patch("libpurecool.dyson.DysonAccount.login", return_value=True)
async def test_setup_component_with_parent_discovery(
    mocked_login, mocked_devices, hass
):
    """Test setup_component using discovery."""
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    assert len(hass.data[dyson.DYSON_DEVICES]) == 2
