"""Tests for ISY994 climate platform."""

from unittest.mock import AsyncMock, MagicMock

from pyisy.constants import (
    CMD_CLIMATE_FAN_SETTING,
    CMD_CLIMATE_MODE,
    ISY_VALUE_UNKNOWN,
    PROP_HEAT_COOL_STATE,
    PROP_HUMIDITY,
    PROP_SETPOINT_COOL,
    PROP_SETPOINT_HEAT,
    PROP_UOM,
    PROTO_INSTEON,
)
from pyisy.nodes import Node

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    FAN_AUTO,
    FAN_OFF,
    FAN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.components.isy994.climate import ISYThermostatEntity
from homeassistant.components.isy994.const import (
    HA_FAN_TO_ISY,
    HA_HVAC_TO_ISY,
    UOM_HVAC_MODE_INSTEON,
    UOM_ISY_CELSIUS,
    UOM_ISY_FAHRENHEIT,
    UOM_ISYV4_NONE,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature


def _make_prop(value: object, uom: str = "", prec: int = 0) -> MagicMock:
    """Return a mock aux property."""
    prop = MagicMock()
    prop.value = value
    prop.uom = uom
    prop.prec = prec
    return prop


def make_node(
    status: object = 700,
    uom: str | list = UOM_HVAC_MODE_INSTEON,
    prec: int = 0,
    protocol: str = PROTO_INSTEON,
    aux_properties: dict | None = None,
) -> MagicMock:
    """Return a minimal mock Node for thermostat tests."""
    node = MagicMock(spec=Node)
    node.status = status
    node.uom = uom
    node.prec = prec
    node.protocol = protocol
    node.address = "1 1"
    node.aux_properties = aux_properties if aux_properties is not None else {}
    node.status_events = MagicMock()
    node.status_events.subscribe.return_value = MagicMock()
    node.control_events = MagicMock()
    node.control_events.subscribe.return_value = MagicMock()
    return node


def make_thermostat_entity(
    node: MagicMock | None = None,
) -> ISYThermostatEntity:
    """Return an ISYThermostatEntity with node injected."""
    node = node or make_node()
    entity = ISYThermostatEntity.__new__(ISYThermostatEntity)
    entity._node = node
    entity._attrs = {}
    entity._uom = node.uom if not isinstance(node.uom, list) else node.uom[0]
    entity.async_write_ha_state = MagicMock()
    entity.hass = MagicMock()
    entity.hass.config.units.temperature_unit = UnitOfTemperature.FAHRENHEIT
    return entity


# ---------------------------------------------------------------------------
# _uom initialisation (via __init__)
# ---------------------------------------------------------------------------


def test_thermostat_uom_string() -> None:
    """_uom is set directly when node.uom is a string."""
    entity = make_thermostat_entity(make_node(uom=UOM_HVAC_MODE_INSTEON))
    assert entity._uom == UOM_HVAC_MODE_INSTEON


def test_thermostat_uom_list() -> None:
    """_uom is set to the first element when node.uom is a list."""
    entity = make_thermostat_entity(make_node(uom=["98", "67"]))
    assert entity._uom == "98"


# ---------------------------------------------------------------------------
# temperature_unit
# ---------------------------------------------------------------------------


def test_temperature_unit_celsius() -> None:
    """temperature_unit returns CELSIUS when PROP_UOM value is UOM_ISY_CELSIUS."""
    node = make_node(aux_properties={PROP_UOM: _make_prop(UOM_ISY_CELSIUS)})
    entity = make_thermostat_entity(node)
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS


def test_temperature_unit_fahrenheit() -> None:
    """temperature_unit returns FAHRENHEIT when PROP_UOM value is UOM_ISY_FAHRENHEIT."""
    node = make_node(aux_properties={PROP_UOM: _make_prop(UOM_ISY_FAHRENHEIT)})
    entity = make_thermostat_entity(node)
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT


def test_temperature_unit_unknown_defaults_fahrenheit() -> None:
    """temperature_unit returns FAHRENHEIT for unrecognised PROP_UOM values."""
    node = make_node(aux_properties={PROP_UOM: _make_prop(99)})
    entity = make_thermostat_entity(node)
    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT


def test_temperature_unit_no_prop_uses_hass_units() -> None:
    """temperature_unit falls back to hass config units when PROP_UOM absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    entity.hass.config.units.temperature_unit = UnitOfTemperature.CELSIUS
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS


# ---------------------------------------------------------------------------
# current_humidity
# ---------------------------------------------------------------------------


def test_current_humidity_none_when_missing() -> None:
    """current_humidity is None when PROP_HUMIDITY is absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    assert entity.current_humidity is None


def test_current_humidity_none_when_unknown() -> None:
    """current_humidity is None when PROP_HUMIDITY value is ISY_VALUE_UNKNOWN."""
    node = make_node(aux_properties={PROP_HUMIDITY: _make_prop(ISY_VALUE_UNKNOWN)})
    entity = make_thermostat_entity(node)
    assert entity.current_humidity is None


def test_current_humidity_integer() -> None:
    """current_humidity returns int(value) when valid."""
    node = make_node(aux_properties={PROP_HUMIDITY: _make_prop(45)})
    entity = make_thermostat_entity(node)
    assert entity.current_humidity == 45


# ---------------------------------------------------------------------------
# hvac_mode
# ---------------------------------------------------------------------------


def test_hvac_mode_off_when_no_mode_property() -> None:
    """hvac_mode is HVACMode.OFF when CMD_CLIMATE_MODE is absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    assert entity.hvac_mode is HVACMode.OFF


def test_hvac_mode_insteon_heat() -> None:
    """hvac_mode maps correctly for Insteon UOM with value 1 (heat)."""
    prop = _make_prop(1, uom=UOM_HVAC_MODE_INSTEON)
    node = make_node(
        protocol=PROTO_INSTEON,
        aux_properties={CMD_CLIMATE_MODE: prop},
    )
    entity = make_thermostat_entity(node)
    assert entity.hvac_mode is HVACMode.HEAT


def test_hvac_mode_empty_uom_insteon_falls_back_to_insteon_table() -> None:
    """hvac_mode uses UOM_HVAC_MODE_INSTEON table when UOM is empty and protocol is Insteon."""
    prop = _make_prop(2, uom="")
    node = make_node(
        protocol=PROTO_INSTEON,
        aux_properties={CMD_CLIMATE_MODE: prop},
    )
    entity = make_thermostat_entity(node)
    assert entity.hvac_mode is HVACMode.COOL


def test_hvac_mode_isyv4_none_uom_insteon_falls_back() -> None:
    """hvac_mode uses UOM_HVAC_MODE_INSTEON table when UOM is UOM_ISYV4_NONE and Insteon."""
    prop = _make_prop(1, uom=UOM_ISYV4_NONE)
    node = make_node(
        protocol=PROTO_INSTEON,
        aux_properties={CMD_CLIMATE_MODE: prop},
    )
    entity = make_thermostat_entity(node)
    assert entity.hvac_mode is HVACMode.HEAT


# ---------------------------------------------------------------------------
# hvac_action
# ---------------------------------------------------------------------------


def test_hvac_action_none_when_missing() -> None:
    """hvac_action is None when PROP_HEAT_COOL_STATE is absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    assert entity.hvac_action is None


def test_hvac_action_heating() -> None:
    """hvac_action returns HVACAction.HEATING for value 1."""
    node = make_node(aux_properties={PROP_HEAT_COOL_STATE: _make_prop(1)})
    entity = make_thermostat_entity(node)
    assert entity.hvac_action is HVACAction.HEATING


def test_hvac_action_cooling() -> None:
    """hvac_action returns HVACAction.COOLING for value 2."""
    node = make_node(aux_properties={PROP_HEAT_COOL_STATE: _make_prop(2)})
    entity = make_thermostat_entity(node)
    assert entity.hvac_action is HVACAction.COOLING


# ---------------------------------------------------------------------------
# target_temperature routing
# ---------------------------------------------------------------------------


def test_target_temperature_cool_mode_returns_high() -> None:
    """target_temperature returns target_temperature_high in COOL mode."""
    setpoint = _make_prop(76, uom=UOM_HVAC_MODE_INSTEON, prec=0)
    node = make_node(
        aux_properties={
            CMD_CLIMATE_MODE: _make_prop(2, uom=UOM_HVAC_MODE_INSTEON),
            PROP_SETPOINT_COOL: setpoint,
        }
    )
    entity = make_thermostat_entity(node)
    assert entity.target_temperature == entity.target_temperature_high


def test_target_temperature_heat_mode_returns_low() -> None:
    """target_temperature returns target_temperature_low in HEAT mode."""
    setpoint = _make_prop(68, uom=UOM_HVAC_MODE_INSTEON, prec=0)
    node = make_node(
        aux_properties={
            CMD_CLIMATE_MODE: _make_prop(1, uom=UOM_HVAC_MODE_INSTEON),
            PROP_SETPOINT_HEAT: setpoint,
        }
    )
    entity = make_thermostat_entity(node)
    assert entity.target_temperature == entity.target_temperature_low


def test_target_temperature_other_mode_is_none() -> None:
    """target_temperature returns None when mode is not HEAT or COOL."""
    node = make_node(
        aux_properties={
            CMD_CLIMATE_MODE: _make_prop(3, uom=UOM_HVAC_MODE_INSTEON),
        }
    )
    entity = make_thermostat_entity(node)
    assert entity.target_temperature is None


# ---------------------------------------------------------------------------
# target_temperature_high / low
# ---------------------------------------------------------------------------


def test_target_temperature_high_none_when_missing() -> None:
    """target_temperature_high is None when PROP_SETPOINT_COOL is absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    assert entity.target_temperature_high is None


def test_target_temperature_low_none_when_missing() -> None:
    """target_temperature_low is None when PROP_SETPOINT_HEAT is absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    assert entity.target_temperature_low is None


# ---------------------------------------------------------------------------
# fan_mode
# ---------------------------------------------------------------------------


def test_fan_mode_off_when_missing() -> None:
    """fan_mode returns FAN_OFF when CMD_CLIMATE_FAN_SETTING is absent."""
    entity = make_thermostat_entity(make_node(aux_properties={}))
    assert entity.fan_mode == FAN_OFF


def test_fan_mode_on() -> None:
    """fan_mode returns FAN_ON for value 7."""
    node = make_node(aux_properties={CMD_CLIMATE_FAN_SETTING: _make_prop(7)})
    entity = make_thermostat_entity(node)
    assert entity.fan_mode == FAN_ON


def test_fan_mode_auto() -> None:
    """fan_mode returns FAN_AUTO for value 8."""
    node = make_node(aux_properties={CMD_CLIMATE_FAN_SETTING: _make_prop(8)})
    entity = make_thermostat_entity(node)
    assert entity.fan_mode == FAN_AUTO


# ---------------------------------------------------------------------------
# async_set_fan_mode / async_set_hvac_mode
# ---------------------------------------------------------------------------


async def test_set_fan_mode_calls_node() -> None:
    """async_set_fan_mode calls set_fan_mode with ISY-mapped value."""
    node = make_node()
    node.set_fan_mode = AsyncMock()
    entity = make_thermostat_entity(node)
    await entity.async_set_fan_mode(FAN_ON)
    node.set_fan_mode.assert_awaited_once_with(HA_FAN_TO_ISY[FAN_ON])
    entity.async_write_ha_state.assert_called_once()


async def test_set_hvac_mode_calls_node() -> None:
    """async_set_hvac_mode calls set_climate_mode with ISY-mapped value."""
    node = make_node()
    node.set_climate_mode = AsyncMock()
    entity = make_thermostat_entity(node)
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    node.set_climate_mode.assert_awaited_once_with(HA_HVAC_TO_ISY[HVACMode.HEAT])
    entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# async_set_temperature
# ---------------------------------------------------------------------------


async def test_set_temperature_single_cool_mode() -> None:
    """ATTR_TEMPERATURE in COOL mode calls set_climate_setpoint_cool."""
    node = make_node(
        aux_properties={CMD_CLIMATE_MODE: _make_prop(2, uom=UOM_HVAC_MODE_INSTEON)}
    )
    node.set_climate_setpoint_cool = AsyncMock()
    node.set_climate_setpoint_heat = AsyncMock()
    entity = make_thermostat_entity(node)
    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 76})
    node.set_climate_setpoint_cool.assert_awaited_once_with(76)
    node.set_climate_setpoint_heat.assert_not_awaited()


async def test_set_temperature_single_heat_mode() -> None:
    """ATTR_TEMPERATURE in HEAT mode calls set_climate_setpoint_heat."""
    node = make_node(
        aux_properties={CMD_CLIMATE_MODE: _make_prop(1, uom=UOM_HVAC_MODE_INSTEON)}
    )
    node.set_climate_setpoint_heat = AsyncMock()
    node.set_climate_setpoint_cool = AsyncMock()
    entity = make_thermostat_entity(node)
    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 68})
    node.set_climate_setpoint_heat.assert_awaited_once_with(68)
    node.set_climate_setpoint_cool.assert_not_awaited()


async def test_set_temperature_range_sets_both() -> None:
    """ATTR_TARGET_TEMP_LOW and HIGH both call the respective setpoint methods."""
    node = make_node(aux_properties={})
    node.set_climate_setpoint_heat = AsyncMock()
    node.set_climate_setpoint_cool = AsyncMock()
    entity = make_thermostat_entity(node)
    await entity.async_set_temperature(
        **{ATTR_TARGET_TEMP_LOW: 65, ATTR_TARGET_TEMP_HIGH: 78}
    )
    node.set_climate_setpoint_heat.assert_awaited_once_with(65)
    node.set_climate_setpoint_cool.assert_awaited_once_with(78)
