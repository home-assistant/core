"""Constants for the kermi integration."""

from homeassistant.components import water_heater

DOMAIN = "kermi"

MODBUS_REGISTERS = {
    "water_heater": {
        "temperature": {"register": 100, "scale_factor": 0.1, "data_type": "int16"},
        "target_temperature": {
            "register": 101,
            "scale_factor": 0.1,
            "data_type": "int16",
        },
        "constant_target_temperature": {
            "register": 102,
            "scale_factor": 0.1,
            "data_type": "int16",
        },
        "single_cycle_heating": {"register": 103, "data_type": "int16"},
        "single_cycle_temperature": {
            "register": 104,
            "scale_factor": 0.1,
            "data_type": "int16",
        },
        "operation_mode": {
            "register": 203,
            "mapping": {
                0: "auto",
                1: water_heater.const.STATE_HEAT_PUMP,
                2: water_heater.const.STATE_PERFORMANCE,
                3: water_heater.const.STATE_ELECTRIC,
            },
            "data_type": "enum",
        },
    },
}
