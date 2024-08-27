"""Constants for the iskra integration."""

DOMAIN = "iskra"
MANUFACTURER = "Iskra d.o.o"

# POWER
ATTR_TOTAL_APPARENT_POWER = "total_apparent_power"
ATTR_TOTAL_REACTIVE_POWER = "total_reactive_power"
ATTR_TOTAL_ACTIVE_POWER = "total_active_power"
ATTR_PHASE1_POWER = "phase1_power"
ATTR_PHASE2_POWER = "phase2_power"
ATTR_PHASE3_POWER = "phase3_power"

# Voltage
ATTR_PHASE1_VOLTAGE = "phase1_voltage"
ATTR_PHASE2_VOLTAGE = "phase2_voltage"
ATTR_PHASE3_VOLTAGE = "phase3_voltage"

# Current
ATTR_PHASE1_CURRENT = "phase1_current"
ATTR_PHASE2_CURRENT = "phase2_current"
ATTR_PHASE3_CURRENT = "phase3_current"

# Frequency
ATTR_FREQUENCY = "frequency"

# Energy
ATTR_TOTAL_ACTIVE_IMPORT = "total_active_import"
ATTR_TOTAL_ACTIVE_EXPORT = "total_active_export"
ATTR_TOTAL_REACTIVE_IMPORT = "total_reactive_import"
ATTR_TOTAL_REACTIVE_EXPORT = "total_reactive_export"
ATTR_TOTAL_APPARENT_ENERGY_IMPORT = "total_apparent_energy_import"
ATTR_TOTAL_APPARENT_ENERGY_EXPORT = "total_apparent_energy_export"

# Non-resettable counters
ATTR_NON_RESETTABLE_COUNTER_NAME = {
    "active_import": ATTR_TOTAL_ACTIVE_IMPORT,
    "active_export": ATTR_TOTAL_ACTIVE_EXPORT,
    "reactive_import": ATTR_TOTAL_REACTIVE_IMPORT,
    "reactive_export": ATTR_TOTAL_REACTIVE_EXPORT,
    "apparent_import": ATTR_TOTAL_APPARENT_ENERGY_IMPORT,
    "apparent_export": ATTR_TOTAL_APPARENT_ENERGY_EXPORT,
}

ATTR_CONNECTED_DEVICES = "connected_devices"


TIMEOUT = 60
