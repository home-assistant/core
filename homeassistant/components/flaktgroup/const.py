"""Constants for flaktgroup component."""
from __future__ import annotations

from enum import Enum, IntEnum

from .modbus_coordinator import ModbusDatapoint, ModbusDatapointType

DOMAIN = "flaktgroup"
MODBUS_HUB = "modbus_hub"
FLAKTGROUP_MODBUS_SLAVE = 2

CONF_DEVICE_INFO = "device_info"
CONF_MODBUS_COORDINATOR = "modbus_coordinator"
CONF_UPDATE_INTERVAL = "update_interval"


class FanModes(IntEnum):
    """Fläktgroup Fan Modes."""

    LOW = 0
    NORMAL = 1
    HIGH = 2


class Presets(IntEnum):
    """Fläktgroup Presets."""

    STOP = 0
    AUTO = 1
    MANUAL = 2
    FIREPLACE = 3


def _flaktgroup_holding_register(address) -> ModbusDatapoint:
    return ModbusDatapoint(
        FLAKTGROUP_MODBUS_SLAVE, ModbusDatapointType.HOLDING_REGISTER, address
    )


def _flaktgroup_coil(address) -> ModbusDatapoint:
    return ModbusDatapoint(FLAKTGROUP_MODBUS_SLAVE, ModbusDatapointType.COIL, address)


class HoldingRegisters(Enum):
    """Fläktgroup Holding Registers."""

    SUPPLY_AIR_TEMPERATURE = _flaktgroup_holding_register(25)
    HUMIDITY_1 = _flaktgroup_holding_register(35)
    TEMPERATURE_SET_POINT = _flaktgroup_holding_register(49)
    MIN_SUPPLY_TEMPERATURE = _flaktgroup_holding_register(54)
    MAX_SUPPLY_TEMPERATURE = _flaktgroup_holding_register(55)

    SET_POINT_CO2 = _flaktgroup_holding_register(73)

    SUPPLY_FAN_CONFIG_LOW = _flaktgroup_holding_register(78)
    SUPPLY_FAN_CONFIG_NORMAL = _flaktgroup_holding_register(79)
    SUPPLY_FAN_CONFIG_HIGH = _flaktgroup_holding_register(80)
    SUPPLY_FAN_CONFIG_COOKER_HOOD = _flaktgroup_holding_register(81)
    SUPPLY_FAN_CONFIG_FIREPLACE = _flaktgroup_holding_register(82)

    EXTRACT_FAN_CONFIG_LOW = _flaktgroup_holding_register(83)
    EXTRACT_FAN_CONFIG_NORMAL = _flaktgroup_holding_register(84)
    EXTRACT_FAN_CONFIG_HIGH = _flaktgroup_holding_register(85)
    EXTRACT_FAN_CONFIG_COOKER_HOOD = _flaktgroup_holding_register(86)
    EXTRACT_FAN_CONFIG_FIREPLACE = _flaktgroup_holding_register(87)

    FAN_MODE = _flaktgroup_holding_register(202)
    PRESET_MODE = _flaktgroup_holding_register(213)
    DIRTY_FILTER_ALARM_TIME = _flaktgroup_holding_register(277)
