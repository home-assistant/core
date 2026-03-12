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

# Conf keys
CONF_HEATING_DEVICE = "heating_device"
CONF_ADDON_MODULES = "addon_modules"
CONF_SLAVE_ID = "slave_id"
CONF_DISCOVERED_SENSORS = "discovered_sensors"
# Maps module_key → list of selected instance labels (e.g. {"heating_circuits": ["HC 1.1", "HC 2.1"]})
CONF_ACTIVE_INSTANCES = "active_instances"

DEFAULT_SLAVE_ID = 1

HEATING_DEVICES = {
    "easyfire": "KWB EasyFire",
    "multifire": "KWB MultiFire",
    "pelletfire_plus": "KWB PelletFire+",
    "combifire": "KWB CombiFire",
    "cf2": "KWB CF 2",
    "cf1_5": "KWB CF 1.5",
    "cf1": "KWB CF 1",
}

# All selectable add-on modules
ADDON_MODULES = {
    "buffer_tank": "Buffer Storage Tank",
    "solar": "Solar",
    "heating_circuits": "Heating Circuits",
    "dhwc": "DHWC (Domestic Hot Water)",
    "circulation": "Circulation",
    "secondary_heating_sources": "Secondary Heating Sources",
    "heat_quantity_meter": "Heat Quantity Meter",
    "boiler_master_slave": "Boiler Master-Slave Circuit",
    "wmm_autonom": "WMM Autonom",
}

# Sensor status values from Modbus ValueTable system_sensor_status_t
SENSOR_STATUS_OK = 2
SENSOR_STATUS_MISSING = 1
SENSOR_STATUS_FAULTY = 0

# Modules that are always active (not selectable)
ALWAYS_ACTIVE_MODULES = ["universal"]

CONF_EXPERT_MODE = "expert_mode"

# Sensor addresses that always receive EntityCategory.DIAGNOSTIC
DIAGNOSTIC_ADDRESSES = {
    9496,   # Modbus heat consumption Max
    24849,  # Modbus Lifetick
    24850,  # Modbus Commit Lifetick
    24851,  # Modbus boiler temperature (Modbus control)
    24852,  # Modbus boiler output (Modbus control)
    24854,  # Modbus boiler request (Modbus control)
    24932,  # Modbus buffer temp top (value)
    24933,  # Modbus buffer temp top (status)
    24934,  # Modbus buffer temp bottom (value)
    24935,  # Modbus buffer temp bottom (status)
}

# Select addresses that are only visible in expert mode
EXPERT_SELECT_ADDRESSES = {
    24583,  # External specification
    24584,  # Boiler program
    24586,  # Automatic ignition Function
}

# KWB address space: registers >= this address are holding registers (func 03).
# Below this threshold are input registers (func 04, read-only sensor data).
MODBUS_HOLDING_REG_START = 24576

# Indexed modules (BUF 0-14, HC 1.1, etc.) — require discovery
INDEXED_MODULES = [
    "buffer_tank",
    "heating_circuits",
    "dhwc",
    "circulation",
    "secondary_heating_sources",
    "solar",
    "heat_quantity_meter",
]


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
    options: dict | None = None
