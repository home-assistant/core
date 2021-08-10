"""Test Z-Wave climate devices."""
import pytest

from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    HVAC_MODES,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SWING_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.components.zwave import climate, const
from homeassistant.components.zwave.climate import (
    AUX_HEAT_ZWAVE_MODE,
    DEFAULT_HVAC_MODES,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from tests.mock.zwave import MockEntityValues, MockNode, MockValue, value_changed


@pytest.fixture
def device(hass, mock_openzwave):
    """Fixture to provide a precreated climate device."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT,
            data_items=[
                HVAC_MODE_OFF,
                HVAC_MODE_HEAT,
                HVAC_MODE_COOL,
                HVAC_MODE_HEAT_COOL,
            ],
            node=node,
        ),
        setpoint_heating=MockValue(data=1, node=node),
        setpoint_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data=CURRENT_HVAC_HEAT, node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_zxt_120(hass, mock_openzwave):
    """Fixture to provide a precreated climate device."""
    node = MockNode(manufacturer_id="5254", product_id="8377")

    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT,
            data_items=[
                HVAC_MODE_OFF,
                HVAC_MODE_HEAT,
                HVAC_MODE_COOL,
                HVAC_MODE_HEAT_COOL,
            ],
            node=node,
        ),
        setpoint_heating=MockValue(data=1, node=node),
        setpoint_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data=CURRENT_HVAC_HEAT, node=node),
        fan_action=MockValue(data=7, node=node),
        zxt_120_swing_mode=MockValue(data="test3", data_items=[6, 7, 8], node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_mapping(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. Test state mapping."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data="Heat",
            data_items=["Off", "Cool", "Heat", "Full Power", "Auto"],
            node=node,
        ),
        setpoint_heating=MockValue(data=1, node=node),
        setpoint_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="heating", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_unknown(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. Test state unknown."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data="Heat",
            data_items=["Off", "Cool", "Heat", "heat_cool", "Abcdefg"],
            node=node,
        ),
        setpoint_heating=MockValue(data=1, node=node),
        setpoint_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="test4", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_heat_cool(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. Test state heat only."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT,
            data_items=[
                HVAC_MODE_OFF,
                HVAC_MODE_HEAT,
                HVAC_MODE_COOL,
                "Heat Eco",
                "Cool Eco",
            ],
            node=node,
        ),
        setpoint_heating=MockValue(data=1, node=node),
        setpoint_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="test4", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_heat_cool_range(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. Target range mode."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT_COOL,
            data_items=[
                HVAC_MODE_OFF,
                HVAC_MODE_HEAT,
                HVAC_MODE_COOL,
                HVAC_MODE_HEAT_COOL,
            ],
            node=node,
        ),
        setpoint_heating=MockValue(data=1, node=node),
        setpoint_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="test4", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_heat_cool_away(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. Target range mode."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT_COOL,
            data_items=[
                HVAC_MODE_OFF,
                HVAC_MODE_HEAT,
                HVAC_MODE_COOL,
                HVAC_MODE_HEAT_COOL,
                PRESET_AWAY,
            ],
            node=node,
        ),
        setpoint_heating=MockValue(data=2, node=node),
        setpoint_cooling=MockValue(data=9, node=node),
        setpoint_away_heating=MockValue(data=1, node=node),
        setpoint_away_cooling=MockValue(data=10, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="test4", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_heat_eco(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. heat/heat eco."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT,
            data_items=[HVAC_MODE_OFF, HVAC_MODE_HEAT, "heat econ"],
            node=node,
        ),
        setpoint_heating=MockValue(data=2, node=node),
        setpoint_eco_heating=MockValue(data=1, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="test4", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_aux_heat(hass, mock_openzwave):
    """Fixture to provide a precreated climate device. aux heat."""
    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT,
            data_items=[HVAC_MODE_OFF, HVAC_MODE_HEAT, "Aux Heat"],
            node=node,
        ),
        setpoint_heating=MockValue(data=2, node=node),
        setpoint_eco_heating=MockValue(data=1, node=node),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data="test4", node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_single_setpoint(hass, mock_openzwave):
    """Fixture to provide a precreated climate device.

    SETPOINT_THERMOSTAT device class.
    """

    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_SETPOINT, data=1, node=node
        ),
        mode=None,
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data=CURRENT_HVAC_HEAT, node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


@pytest.fixture
def device_single_setpoint_with_mode(hass, mock_openzwave):
    """Fixture to provide a precreated climate device.

    SETPOINT_THERMOSTAT device class with COMMAND_CLASS_THERMOSTAT_MODE command class
    """

    node = MockNode()
    values = MockEntityValues(
        primary=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_SETPOINT, data=1, node=node
        ),
        mode=MockValue(
            command_class=const.COMMAND_CLASS_THERMOSTAT_MODE,
            data=HVAC_MODE_HEAT,
            data_items=[HVAC_MODE_OFF, HVAC_MODE_HEAT],
            node=node,
        ),
        temperature=MockValue(data=5, node=node, units=None),
        fan_mode=MockValue(data="test2", data_items=[3, 4, 5], node=node),
        operating_state=MockValue(data=CURRENT_HVAC_HEAT, node=node),
        fan_action=MockValue(data=7, node=node),
    )
    device = climate.get_device(hass, node=node, values=values, node_config={})

    yield device


def test_get_device_detects_none(hass, mock_openzwave):
    """Test get_device returns None."""
    node = MockNode()
    value = MockValue(data=0, node=node)
    values = MockEntityValues(primary=value)

    device = climate.get_device(hass, node=node, values=values, node_config={})
    assert device is None


def test_get_device_detects_multiple_setpoint_device(device):
    """Test get_device returns a Z-Wave multiple setpoint device."""
    assert isinstance(device, climate.ZWaveClimateMultipleSetpoint)


def test_get_device_detects_single_setpoint_device(device_single_setpoint):
    """Test get_device returns a Z-Wave single setpoint device."""
    assert isinstance(device_single_setpoint, climate.ZWaveClimateSingleSetpoint)


def test_default_hvac_modes():
    """Test whether all hvac modes are included in default_hvac_modes."""
    for hvac_mode in HVAC_MODES:
        assert hvac_mode in DEFAULT_HVAC_MODES


def test_supported_features(device):
    """Test supported features flags."""
    assert (
        device.supported_features
        == SUPPORT_FAN_MODE
        + SUPPORT_TARGET_TEMPERATURE
        + SUPPORT_TARGET_TEMPERATURE_RANGE
    )


def test_supported_features_temp_range(device_heat_cool_range):
    """Test supported features flags with target temp range."""
    device = device_heat_cool_range
    assert (
        device.supported_features
        == SUPPORT_FAN_MODE
        + SUPPORT_TARGET_TEMPERATURE
        + SUPPORT_TARGET_TEMPERATURE_RANGE
    )


def test_supported_features_preset_mode(device_mapping):
    """Test supported features flags with swing mode."""
    device = device_mapping
    assert (
        device.supported_features
        == SUPPORT_FAN_MODE
        + SUPPORT_TARGET_TEMPERATURE
        + SUPPORT_TARGET_TEMPERATURE_RANGE
        + SUPPORT_PRESET_MODE
    )


def test_supported_features_preset_mode_away(device_heat_cool_away):
    """Test supported features flags with swing mode."""
    device = device_heat_cool_away
    assert (
        device.supported_features
        == SUPPORT_FAN_MODE
        + SUPPORT_TARGET_TEMPERATURE
        + SUPPORT_TARGET_TEMPERATURE_RANGE
        + SUPPORT_PRESET_MODE
    )


def test_supported_features_swing_mode(device_zxt_120):
    """Test supported features flags with swing mode."""
    device = device_zxt_120
    assert (
        device.supported_features
        == SUPPORT_FAN_MODE
        + SUPPORT_TARGET_TEMPERATURE
        + SUPPORT_TARGET_TEMPERATURE_RANGE
        + SUPPORT_SWING_MODE
    )


def test_supported_features_aux_heat(device_aux_heat):
    """Test supported features flags with aux heat."""
    device = device_aux_heat
    assert (
        device.supported_features
        == SUPPORT_FAN_MODE + SUPPORT_TARGET_TEMPERATURE + SUPPORT_AUX_HEAT
    )


def test_supported_features_single_setpoint(device_single_setpoint):
    """Test supported features flags for SETPOINT_THERMOSTAT."""
    device = device_single_setpoint
    assert device.supported_features == SUPPORT_FAN_MODE + SUPPORT_TARGET_TEMPERATURE


def test_supported_features_single_setpoint_with_mode(device_single_setpoint_with_mode):
    """Test supported features flags for SETPOINT_THERMOSTAT."""
    device = device_single_setpoint_with_mode
    assert device.supported_features == SUPPORT_FAN_MODE + SUPPORT_TARGET_TEMPERATURE


def test_zxt_120_swing_mode(device_zxt_120):
    """Test operation of the zxt 120 swing mode."""
    device = device_zxt_120

    assert device.swing_modes == [6, 7, 8]
    assert device._zxt_120 == 1

    # Test set mode
    assert device.values.zxt_120_swing_mode.data == "test3"
    device.set_swing_mode("test_swing_set")
    assert device.values.zxt_120_swing_mode.data == "test_swing_set"

    # Test mode changed
    value_changed(device.values.zxt_120_swing_mode)
    assert device.swing_mode == "test_swing_set"
    device.values.zxt_120_swing_mode.data = "test_swing_updated"
    value_changed(device.values.zxt_120_swing_mode)
    assert device.swing_mode == "test_swing_updated"


def test_temperature_unit(device):
    """Test temperature unit."""
    assert device.temperature_unit == TEMP_CELSIUS
    device.values.temperature.units = "F"
    value_changed(device.values.temperature)
    assert device.temperature_unit == TEMP_FAHRENHEIT
    device.values.temperature.units = "C"
    value_changed(device.values.temperature)
    assert device.temperature_unit == TEMP_CELSIUS


def test_data_lists(device):
    """Test data lists from zwave value items."""
    assert device.fan_modes == [3, 4, 5]
    assert device.hvac_modes == [
        HVAC_MODE_OFF,
        HVAC_MODE_HEAT,
        HVAC_MODE_COOL,
        HVAC_MODE_HEAT_COOL,
    ]
    assert device.preset_modes == []
    device.values.primary = None
    assert device.preset_modes == []


def test_data_lists_single_setpoint(device_single_setpoint):
    """Test data lists from zwave value items."""
    device = device_single_setpoint
    assert device.fan_modes == [3, 4, 5]
    assert device.hvac_modes == []
    assert device.preset_modes == []


def test_data_lists_single_setpoint_with_mode(device_single_setpoint_with_mode):
    """Test data lists from zwave value items."""
    device = device_single_setpoint_with_mode
    assert device.fan_modes == [3, 4, 5]
    assert device.hvac_modes == [HVAC_MODE_OFF, HVAC_MODE_HEAT]
    assert device.preset_modes == []


def test_data_lists_mapping(device_mapping):
    """Test data lists from zwave value items."""
    device = device_mapping
    assert device.hvac_modes == ["off", "cool", "heat", "heat_cool"]
    assert device.preset_modes == ["boost", "none"]
    device.values.primary = None
    assert device.preset_modes == []


def test_target_value_set(device):
    """Test values changed for climate device."""
    assert device.values.setpoint_heating.data == 1
    assert device.values.setpoint_cooling.data == 10
    device.set_temperature()
    assert device.values.setpoint_heating.data == 1
    assert device.values.setpoint_cooling.data == 10
    device.set_temperature(**{ATTR_TEMPERATURE: 2})
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 10
    device.set_hvac_mode(HVAC_MODE_COOL)
    value_changed(device.values.primary)
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 10
    device.set_temperature(**{ATTR_TEMPERATURE: 9})
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 9


def test_target_value_set_range(device_heat_cool_range):
    """Test values changed for climate device."""
    device = device_heat_cool_range
    assert device.values.setpoint_heating.data == 1
    assert device.values.setpoint_cooling.data == 10
    device.set_temperature()
    assert device.values.setpoint_heating.data == 1
    assert device.values.setpoint_cooling.data == 10
    device.set_temperature(**{ATTR_TARGET_TEMP_LOW: 2})
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 10
    device.set_temperature(**{ATTR_TARGET_TEMP_HIGH: 9})
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 9
    device.set_temperature(**{ATTR_TARGET_TEMP_LOW: 3, ATTR_TARGET_TEMP_HIGH: 8})
    assert device.values.setpoint_heating.data == 3
    assert device.values.setpoint_cooling.data == 8


def test_target_value_set_range_away(device_heat_cool_away):
    """Test values changed for climate device."""
    device = device_heat_cool_away
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 9
    assert device.values.setpoint_away_heating.data == 1
    assert device.values.setpoint_away_cooling.data == 10
    device.set_preset_mode(PRESET_AWAY)
    device.set_temperature(**{ATTR_TARGET_TEMP_LOW: 0, ATTR_TARGET_TEMP_HIGH: 11})
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_cooling.data == 9
    assert device.values.setpoint_away_heating.data == 0
    assert device.values.setpoint_away_cooling.data == 11


def test_target_value_set_eco(device_heat_eco):
    """Test values changed for climate device."""
    device = device_heat_eco
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_eco_heating.data == 1
    device.set_preset_mode("heat econ")
    device.set_temperature(**{ATTR_TEMPERATURE: 0})
    assert device.values.setpoint_heating.data == 2
    assert device.values.setpoint_eco_heating.data == 0


def test_target_value_set_single_setpoint(device_single_setpoint):
    """Test values changed for climate device."""
    device = device_single_setpoint
    assert device.values.primary.data == 1
    device.set_temperature(**{ATTR_TEMPERATURE: 2})
    assert device.values.primary.data == 2


def test_operation_value_set(device):
    """Test values changed for climate device."""
    assert device.values.primary.data == HVAC_MODE_HEAT
    device.set_hvac_mode(HVAC_MODE_COOL)
    assert device.values.primary.data == HVAC_MODE_COOL
    device.set_preset_mode(PRESET_ECO)
    assert device.values.primary.data == PRESET_ECO
    device.set_preset_mode(PRESET_NONE)
    assert device.values.primary.data == HVAC_MODE_HEAT_COOL
    device.values.primary = None
    device.set_hvac_mode("test_set_failes")
    assert device.values.primary is None
    device.set_preset_mode("test_set_failes")
    assert device.values.primary is None


def test_operation_value_set_mapping(device_mapping):
    """Test values changed for climate device. Mapping."""
    device = device_mapping
    assert device.values.primary.data == "Heat"
    device.set_hvac_mode(HVAC_MODE_COOL)
    assert device.values.primary.data == "Cool"
    device.set_hvac_mode(HVAC_MODE_OFF)
    assert device.values.primary.data == "Off"
    device.set_preset_mode(PRESET_BOOST)
    assert device.values.primary.data == "Full Power"
    device.set_preset_mode(PRESET_ECO)
    assert device.values.primary.data == "eco"


def test_operation_value_set_unknown(device_unknown):
    """Test values changed for climate device. Unknown."""
    device = device_unknown
    assert device.values.primary.data == "Heat"
    device.set_preset_mode("Abcdefg")
    assert device.values.primary.data == "Abcdefg"
    device.set_preset_mode(PRESET_NONE)
    assert device.values.primary.data == HVAC_MODE_HEAT_COOL


def test_operation_value_set_heat_cool(device_heat_cool):
    """Test values changed for climate device. Heat/Cool only."""
    device = device_heat_cool
    assert device.values.primary.data == HVAC_MODE_HEAT
    device.set_preset_mode("Heat Eco")
    assert device.values.primary.data == "Heat Eco"
    device.set_preset_mode(PRESET_NONE)
    assert device.values.primary.data == HVAC_MODE_HEAT
    device.set_preset_mode("Cool Eco")
    assert device.values.primary.data == "Cool Eco"
    device.set_preset_mode(PRESET_NONE)
    assert device.values.primary.data == HVAC_MODE_COOL


def test_fan_mode_value_set(device):
    """Test values changed for climate device."""
    assert device.values.fan_mode.data == "test2"
    device.set_fan_mode("test_fan_set")
    assert device.values.fan_mode.data == "test_fan_set"
    device.values.fan_mode = None
    device.set_fan_mode("test_fan_set_failes")
    assert device.values.fan_mode is None


def test_target_value_changed(device):
    """Test values changed for climate device."""
    assert device.target_temperature == 1
    device.values.setpoint_heating.data = 2
    value_changed(device.values.setpoint_heating)
    assert device.target_temperature == 2
    device.values.primary.data = HVAC_MODE_COOL
    value_changed(device.values.primary)
    assert device.target_temperature == 10
    device.values.setpoint_cooling.data = 9
    value_changed(device.values.setpoint_cooling)
    assert device.target_temperature == 9


def test_target_range_changed(device_heat_cool_range):
    """Test values changed for climate device."""
    device = device_heat_cool_range
    assert device.target_temperature_low == 1
    assert device.target_temperature_high == 10
    device.values.setpoint_heating.data = 2
    value_changed(device.values.setpoint_heating)
    assert device.target_temperature_low == 2
    assert device.target_temperature_high == 10
    device.values.setpoint_cooling.data = 9
    value_changed(device.values.setpoint_cooling)
    assert device.target_temperature_low == 2
    assert device.target_temperature_high == 9


def test_target_changed_preset_range(device_heat_cool_away):
    """Test values changed for climate device."""
    device = device_heat_cool_away
    assert device.target_temperature_low == 2
    assert device.target_temperature_high == 9
    device.values.primary.data = PRESET_AWAY
    value_changed(device.values.primary)
    assert device.target_temperature_low == 1
    assert device.target_temperature_high == 10
    device.values.setpoint_away_heating.data = 0
    value_changed(device.values.setpoint_away_heating)
    device.values.setpoint_away_cooling.data = 11
    value_changed(device.values.setpoint_away_cooling)
    assert device.target_temperature_low == 0
    assert device.target_temperature_high == 11
    device.values.primary.data = HVAC_MODE_HEAT_COOL
    value_changed(device.values.primary)
    assert device.target_temperature_low == 2
    assert device.target_temperature_high == 9


def test_target_changed_eco(device_heat_eco):
    """Test values changed for climate device."""
    device = device_heat_eco
    assert device.target_temperature == 2
    device.values.primary.data = "heat econ"
    value_changed(device.values.primary)
    assert device.target_temperature == 1
    device.values.setpoint_eco_heating.data = 0
    value_changed(device.values.setpoint_eco_heating)
    assert device.target_temperature == 0
    device.values.primary.data = HVAC_MODE_HEAT
    value_changed(device.values.primary)
    assert device.target_temperature == 2


def test_target_changed_with_mode(device):
    """Test values changed for climate device."""
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.target_temperature == 1
    device.values.primary.data = HVAC_MODE_COOL
    value_changed(device.values.primary)
    assert device.target_temperature == 10
    device.values.primary.data = HVAC_MODE_HEAT_COOL
    value_changed(device.values.primary)
    assert device.target_temperature_low == 1
    assert device.target_temperature_high == 10


def test_target_value_changed_single_setpoint(device_single_setpoint):
    """Test values changed for climate device."""
    device = device_single_setpoint
    assert device.target_temperature == 1
    device.values.primary.data = 2
    value_changed(device.values.primary)
    assert device.target_temperature == 2


def test_temperature_value_changed(device):
    """Test values changed for climate device."""
    assert device.current_temperature == 5
    device.values.temperature.data = 3
    value_changed(device.values.temperature)
    assert device.current_temperature == 3


def test_operation_value_changed(device):
    """Test values changed for climate device."""
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = HVAC_MODE_COOL
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_COOL
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = HVAC_MODE_OFF
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_OFF
    assert device.preset_mode == PRESET_NONE
    device.values.primary = None
    assert device.hvac_mode == HVAC_MODE_HEAT_COOL
    assert device.preset_mode == PRESET_NONE


def test_operation_value_changed_preset(device_mapping):
    """Test preset changed for climate device."""
    device = device_mapping
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = PRESET_ECO
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_HEAT_COOL
    assert device.preset_mode == PRESET_ECO


def test_operation_value_changed_mapping(device_mapping):
    """Test values changed for climate device. Mapping."""
    device = device_mapping
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = "Off"
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_OFF
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = "Cool"
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_COOL
    assert device.preset_mode == PRESET_NONE


def test_operation_value_changed_mapping_preset(device_mapping):
    """Test values changed for climate device. Mapping with presets."""
    device = device_mapping
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = "Full Power"
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_HEAT_COOL
    assert device.preset_mode == PRESET_BOOST
    device.values.primary = None
    assert device.hvac_mode == HVAC_MODE_HEAT_COOL
    assert device.preset_mode == PRESET_NONE


def test_operation_value_changed_unknown(device_unknown):
    """Test preset changed for climate device. Unknown."""
    device = device_unknown
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = "Abcdefg"
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_HEAT_COOL
    assert device.preset_mode == "Abcdefg"


def test_operation_value_changed_heat_cool(device_heat_cool):
    """Test preset changed for climate device. Heat/Cool only."""
    device = device_heat_cool
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == PRESET_NONE
    device.values.primary.data = "Cool Eco"
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_COOL
    assert device.preset_mode == "Cool Eco"
    device.values.primary.data = "Heat Eco"
    value_changed(device.values.primary)
    assert device.hvac_mode == HVAC_MODE_HEAT
    assert device.preset_mode == "Heat Eco"


def test_fan_mode_value_changed(device):
    """Test values changed for climate device."""
    assert device.fan_mode == "test2"
    device.values.fan_mode.data = "test_updated_fan"
    value_changed(device.values.fan_mode)
    assert device.fan_mode == "test_updated_fan"


def test_hvac_action_value_changed(device):
    """Test values changed for climate device."""
    assert device.hvac_action == CURRENT_HVAC_HEAT
    device.values.operating_state.data = CURRENT_HVAC_COOL
    value_changed(device.values.operating_state)
    assert device.hvac_action == CURRENT_HVAC_COOL


def test_hvac_action_value_changed_mapping(device_mapping):
    """Test values changed for climate device."""
    device = device_mapping
    assert device.hvac_action == CURRENT_HVAC_HEAT
    device.values.operating_state.data = "cooling"
    value_changed(device.values.operating_state)
    assert device.hvac_action == CURRENT_HVAC_COOL


def test_hvac_action_value_changed_unknown(device_unknown):
    """Test values changed for climate device."""
    device = device_unknown
    assert device.hvac_action == "test4"
    device.values.operating_state.data = "another_hvac_action"
    value_changed(device.values.operating_state)
    assert device.hvac_action == "another_hvac_action"


def test_fan_action_value_changed(device):
    """Test values changed for climate device."""
    assert device.extra_state_attributes[climate.ATTR_FAN_ACTION] == 7
    device.values.fan_action.data = 9
    value_changed(device.values.fan_action)
    assert device.extra_state_attributes[climate.ATTR_FAN_ACTION] == 9


def test_aux_heat_unsupported_set(device):
    """Test aux heat for climate device."""
    assert device.values.primary.data == HVAC_MODE_HEAT
    device.turn_aux_heat_on()
    assert device.values.primary.data == HVAC_MODE_HEAT
    device.turn_aux_heat_off()
    assert device.values.primary.data == HVAC_MODE_HEAT


def test_aux_heat_unsupported_value_changed(device):
    """Test aux heat for climate device."""
    assert device.is_aux_heat is None
    device.values.primary.data = HVAC_MODE_HEAT
    value_changed(device.values.primary)
    assert device.is_aux_heat is None


def test_aux_heat_set(device_aux_heat):
    """Test aux heat for climate device."""
    device = device_aux_heat
    assert device.values.primary.data == HVAC_MODE_HEAT
    device.turn_aux_heat_on()
    assert device.values.primary.data == AUX_HEAT_ZWAVE_MODE
    device.turn_aux_heat_off()
    assert device.values.primary.data == HVAC_MODE_HEAT


def test_aux_heat_value_changed(device_aux_heat):
    """Test aux heat for climate device."""
    device = device_aux_heat
    assert device.is_aux_heat is False
    device.values.primary.data = AUX_HEAT_ZWAVE_MODE
    value_changed(device.values.primary)
    assert device.is_aux_heat is True
    device.values.primary.data = HVAC_MODE_HEAT
    value_changed(device.values.primary)
    assert device.is_aux_heat is False
