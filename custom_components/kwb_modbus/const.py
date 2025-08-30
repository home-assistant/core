"""Constants for the KWB Modbus integration."""

from dataclasses import dataclass
from enum import Enum

from homeassistant.components.sensor import SensorEntityDescription

DOMAIN = "kwb_modbus"

# Default values for configuration
DEFAULT_SCAN_INTERVAL = 30  # Standard update interval in seconds
DEFAULT_PORT = 502  # Default port for Modbus TCP

READ_COILS = 1  # read_coils command
READ_DISCRETE_INPUTS = 2  # read_discrete_inputs command
READ_HOLDING_REGISTERS = 3  # read_holding_registers command
READ_INPUT_REGISTERS = 4  # read_input_registers command
WRITE_SINGLE_REGISTER = 6  # write_register command
WRITE_MULTIPLE_COILS = 15  # write_coils command
WRITE_MULTIPLE_REGISTERS = 16  # write_registers command

HEATING_DEVICES = {
    "easyfire": "KWB Easyfire",
    "multifire": "KWB Multifire",
    "pelletfire_plus": "KWB Pelletfire+",
    "combifire": "KWB Combifire",
}


class ModbusDataType(Enum):
    """Enum for Modbus data types."""

    UINT16 = "u16"
    UINT32 = "u32"
    INT16 = "s16"


@dataclass
class ModbusSensorEntityDescription(SensorEntityDescription):
    """Describes Modbus sensor entity."""

    register: int = -1
    register_function: int = READ_INPUT_REGISTERS
    scale: float = 1
    number_of_registries: int = 1
    data_type: ModbusDataType = None
    status_sensor: str = None
    is_status_sensor: bool = False
