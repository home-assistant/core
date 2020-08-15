"""Test the Dyson fan component."""
import json
import unittest

from libpurecool.const import (
    FanPower,
    FanSpeed,
    FanState,
    FocusMode,
    HeatMode,
    HeatState,
    HeatTarget,
)
from libpurecool.dyson_pure_hotcool import DysonPureHotCool
from libpurecool.dyson_pure_hotcool_link import DysonPureHotCoolLink
from libpurecool.dyson_pure_state import DysonPureHotCoolState
from libpurecool.dyson_pure_state_v2 import DysonPureHotCoolV2State

from homeassistant.components import dyson as dyson_parent
from homeassistant.components.climate import (
    DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
)
from homeassistant.components.dyson import climate as dyson
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.setup import async_setup_component

from .common import load_mock_device

from tests.async_mock import MagicMock, Mock, patch
from tests.common import get_test_home_assistant


class MockDysonState(DysonPureHotCoolState):
    """Mock Dyson state."""

    def __init__(self):
        """Create new Mock Dyson State."""


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


def _get_dyson_purehotcool_device():
    """Return a valid device as provided by the Dyson web services."""
    device = Mock(spec=DysonPureHotCool)
    load_mock_device(device)
    device.name = "Living room"
    device.state.heat_target = "0000"
    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.fan_power = FanPower.POWER_OFF.value
    device.environmental_state.humidity = 42
    device.environmental_state.temperature = 298
    return device


def _get_device_with_no_state():
    """Return a device with no state."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state = None
    device.environmental_state = None
    return device


def _get_device_off():
    """Return a device with state off."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    return device


def _get_device_focus():
    """Return a device with fan state of focus mode."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_ON.value
    return device


def _get_device_diffuse():
    """Return a device with fan state of diffuse mode."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    return device


def _get_device_cool():
    """Return a device with state of cooling."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.focus_mode = FocusMode.FOCUS_OFF.value
    device.state.heat_target = HeatTarget.celsius(12)
    device.state.heat_mode = HeatMode.HEAT_OFF.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    return device


def _get_device_heat_off():
    """Return a device with state of heat reached target."""
    device = Mock(spec=DysonPureHotCoolLink)
    load_mock_device(device)
    device.state.heat_mode = HeatMode.HEAT_ON.value
    device.state.heat_state = HeatState.HEAT_STATE_OFF.value
    return device


def _get_device_heat_on():
    """Return a device with state of heating."""
    device = Mock(spec=DysonPureHotCoolLink)
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
        add_devices = MagicMock()
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
        add_devices = MagicMock()
        dyson.setup_platform(self.hass, None, add_devices, discovery_info={})
        assert add_devices.called

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
        entity = dyson.DysonPureHotCoolLinkEntity(device)
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
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        entity.schedule_update_ha_state = Mock()

        kwargs = {ATTR_TEMPERATURE: 23}
        entity.set_temperature(**kwargs)
        set_config = device.set_configuration
        set_config.assert_called_with(
            heat_mode=HeatMode.HEAT_ON, heat_target=HeatTarget.celsius(23)
        )

    def test_dyson_set_fan_mode(self):
        """Test set fan mode."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
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
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert len(entity.fan_modes) == 2
        assert dyson.FAN_FOCUS in entity.fan_modes
        assert dyson.FAN_DIFFUSE in entity.fan_modes

    def test_dyson_fan_mode_focus(self):
        """Test fan focus mode."""
        device = _get_device_focus()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.fan_mode == dyson.FAN_FOCUS

    def test_dyson_fan_mode_diffuse(self):
        """Test fan diffuse mode."""
        device = _get_device_diffuse()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.fan_mode == dyson.FAN_DIFFUSE

    def test_dyson_set_hvac_mode(self):
        """Test set operation mode."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
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
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert len(entity.hvac_modes) == 2
        assert dyson.HVAC_MODE_HEAT in entity.hvac_modes
        assert dyson.HVAC_MODE_COOL in entity.hvac_modes

    def test_dyson_heat_off(self):
        """Test turn off heat."""
        device = _get_device_heat_off()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        entity.set_hvac_mode(dyson.HVAC_MODE_COOL)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_OFF)

    def test_dyson_heat_on(self):
        """Test turn on heat."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        entity.set_hvac_mode(dyson.HVAC_MODE_HEAT)
        set_config = device.set_configuration
        set_config.assert_called_with(heat_mode=HeatMode.HEAT_ON)

    def test_dyson_heat_value_on(self):
        """Test get heat value on."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.hvac_mode == dyson.HVAC_MODE_HEAT

    def test_dyson_heat_value_off(self):
        """Test get heat value off."""
        device = _get_device_cool()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.hvac_mode == dyson.HVAC_MODE_COOL

    def test_dyson_heat_value_idle(self):
        """Test get heat value idle."""
        device = _get_device_heat_off()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.hvac_mode == dyson.HVAC_MODE_HEAT
        assert entity.hvac_action == dyson.CURRENT_HVAC_IDLE

    def test_on_message(self):
        """Test when message is received."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        entity.schedule_update_ha_state = Mock()
        entity.on_message(MockDysonState())
        entity.schedule_update_ha_state.assert_called_with()

    def test_general_properties(self):
        """Test properties of entity."""
        device = _get_device_with_no_state()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.should_poll is False
        assert entity.supported_features == dyson.SUPPORT_FLAGS
        assert entity.temperature_unit == TEMP_CELSIUS

    def test_property_current_humidity(self):
        """Test properties of current humidity."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.current_humidity == 53

    def test_property_current_humidity_with_invalid_env_state(self):
        """Test properties of current humidity with invalid env state."""
        device = _get_device_off()
        device.environmental_state.humidity = 0
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.current_humidity is None

    def test_property_current_humidity_without_env_state(self):
        """Test properties of current humidity without env state."""
        device = _get_device_with_no_state()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.current_humidity is None

    def test_property_current_temperature(self):
        """Test properties of current temperature."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        # Result should be in celsius, hence then subtraction of 273.
        assert entity.current_temperature == 289 - 273

    def test_property_target_temperature(self):
        """Test properties of target temperature."""
        device = _get_device_heat_on()
        entity = dyson.DysonPureHotCoolLinkEntity(device)
        assert entity.target_temperature == 23


@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_heat_on(), _get_device_cool()],
)
@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
async def test_setup_component_with_parent_discovery(
    mocked_login, mocked_devices, hass
):
    """Test setup_component using discovery."""
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("climate")
    assert len(entity_ids) == 2


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_component_setup_only_once(devices, login, hass):
    """Test if entities are created only once."""
    config = _get_config()
    await async_setup_component(hass, dyson_parent.DOMAIN, config)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("climate")
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state.name == "Living room"


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_device_off()],
)
async def test_purehotcoollink_component_setup_only_once(devices, login, hass):
    """Test if entities are created only once."""
    config = _get_config()
    await async_setup_component(hass, dyson_parent.DOMAIN, config)
    await hass.async_block_till_done()

    entity_ids = hass.states.async_entity_ids("climate")
    assert len(entity_ids) == 1
    state = hass.states.get(entity_ids[0])
    assert state.name == "Temp Name"


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_update_state(devices, login, hass):
    """Test state update."""
    device = devices.return_value[0]
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()
    event = {
        "msg": "CURRENT-STATE",
        "product-state": {
            "fpwr": "ON",
            "fdir": "OFF",
            "auto": "OFF",
            "oscs": "ON",
            "oson": "ON",
            "nmod": "OFF",
            "rhtm": "ON",
            "fnst": "FAN",
            "ercd": "11E1",
            "wacd": "NONE",
            "nmdv": "0004",
            "fnsp": "0002",
            "bril": "0002",
            "corf": "ON",
            "cflr": "0085",
            "hflr": "0095",
            "sltm": "OFF",
            "osal": "0045",
            "osau": "0095",
            "ancp": "CUST",
            "tilt": "OK",
            "hsta": "HEAT",
            "hmax": "2986",
            "hmod": "HEAT",
        },
    }
    device.state = DysonPureHotCoolV2State(json.dumps(event))

    for call in device.add_message_listener.call_args_list:
        callback = call[0][0]
        if type(callback.__self__) == dyson.DysonPureHotCoolEntity:
            callback(device.state)

    await hass.async_block_till_done()
    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_TEMPERATURE] == 25
    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_HEAT


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_empty_env_attributes(devices, login, hass):
    """Test empty environmental state update."""
    device = devices.return_value[0]
    device.environmental_state.temperature = None
    device.environmental_state.humidity = None
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert ATTR_CURRENT_HUMIDITY not in attributes


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_fan_state_off(devices, login, hass):
    """Test device fan state off."""
    device = devices.return_value[0]
    device.state.fan_state = FanState.FAN_OFF.value
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_FAN_MODE] == FAN_OFF


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_hvac_action_cool(devices, login, hass):
    """Test device HVAC action cool."""
    device = devices.return_value[0]
    device.state.fan_power = FanPower.POWER_ON.value
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_COOL


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_hvac_action_idle(devices, login, hass):
    """Test device HVAC action idle."""
    device = devices.return_value[0]
    device.state.fan_power = FanPower.POWER_ON.value
    device.state.heat_mode = HeatMode.HEAT_ON.value
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room")
    attributes = state.attributes

    assert attributes[ATTR_HVAC_ACTION] == CURRENT_HVAC_IDLE


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_set_temperature(devices, login, hass):
    """Test set temperature."""
    device = devices.return_value[0]
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()
    state = hass.states.get("climate.living_room")
    attributes = state.attributes
    min_temp = attributes["min_temp"]
    max_temp = attributes["max_temp"]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.bed_room", ATTR_TEMPERATURE: 23},
        True,
    )
    device.set_heat_target.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: 23},
        True,
    )
    assert device.set_heat_target.call_count == 1
    device.set_heat_target.assert_called_with("2960")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: min_temp - 1},
        True,
    )
    assert device.set_heat_target.call_count == 2
    device.set_heat_target.assert_called_with(HeatTarget.celsius(min_temp))

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_TEMPERATURE: max_temp + 1},
        True,
    )
    assert device.set_heat_target.call_count == 3
    device.set_heat_target.assert_called_with(HeatTarget.celsius(max_temp))


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_set_fan_mode(devices, login, hass):
    """Test set fan mode."""
    device = devices.return_value[0]
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.bed_room", ATTR_FAN_MODE: FAN_OFF},
        True,
    )
    device.turn_off.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_OFF},
        True,
    )
    assert device.turn_off.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_LOW},
        True,
    )
    assert device.set_fan_speed.call_count == 1
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_4)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_MEDIUM},
        True,
    )
    assert device.set_fan_speed.call_count == 2
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_7)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_HIGH},
        True,
    )
    assert device.set_fan_speed.call_count == 3
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_10)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_FAN_MODE: FAN_AUTO},
        True,
    )
    assert device.set_fan_speed.call_count == 4
    device.set_fan_speed.assert_called_with(FanSpeed.FAN_SPEED_AUTO)


@patch("homeassistant.components.dyson.DysonAccount.login", return_value=True)
@patch(
    "homeassistant.components.dyson.DysonAccount.devices",
    return_value=[_get_dyson_purehotcool_device()],
)
async def test_purehotcool_set_hvac_mode(devices, login, hass):
    """Test set HVAC mode."""
    device = devices.return_value[0]
    await async_setup_component(hass, dyson_parent.DOMAIN, _get_config())
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.bed_room", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        True,
    )
    device.turn_off.assert_not_called()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVAC_MODE_OFF},
        True,
    )
    assert device.turn_off.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVAC_MODE_HEAT},
        True,
    )
    assert device.turn_on.call_count == 1
    assert device.enable_heat_mode.call_count == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.living_room", ATTR_HVAC_MODE: HVAC_MODE_COOL},
        True,
    )
    assert device.turn_on.call_count == 2
    assert device.disable_heat_mode.call_count == 1
