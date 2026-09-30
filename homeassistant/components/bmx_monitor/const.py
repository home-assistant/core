"""Constants for the BM2 battery monitor integration."""

DOMAIN = "bmx_monitor"

CONF_BATTERY_TYPE = "battery_type"
DEFAULT_BATTERY_TYPE = "Automatic (via BM2)"
CONF_RATE_LIMIT_MODE = "rate_limit_mode"
DEFAULT_RATE_LIMIT_MODE = "never"
CONF_RATE_LIMIT = "rate_limit"
DEFAULT_RATE_LIMIT = 60
CONF_CUSTOM_BATTERY_CHEMISTRY = "custom_battery_chemistry"
DEFAULT_CUSTOM_BATTERY_CHEMISTRY = "Custom battery"
CONF_CUSTOM_CRITICAL_VOLTAGE = "custom_critical_voltage"
DEFAULT_CUSTOM_CRITICAL_VOLTAGE = 12.06
CONF_CUSTOM_LOW_VOLTAGE = "custom_low_voltage"
DEFAULT_CUSTOM_LOW_VOLTAGE = 12.2
CONF_CUSTOM_FIFTY_PERCENT_VOLTAGE = "custom_fifty_percent_voltage"
DEFAULT_CUSTOM_FIFTY_PERCENT_VOLTAGE = 12.3
CONF_CUSTOM_HUNDRED_PERCENT_VOLTAGE = "custom_hundred_percent_voltage"
DEFAULT_CUSTOM_HUNDRED_PERCENT_VOLTAGE = 12.7
CONF_CUSTOM_FLOATING_VOLTAGE = "custom_floating_voltage"
DEFAULT_CUSTOM_FLOATING_VOLTAGE = 13.7
CONF_CUSTOM_CHARGING_VOLTAGE = "custom_charging_voltage"
DEFAULT_CUSTOM_CHARGING_VOLTAGE = 14.5
CONF_CUSTOM_NUMPY_VOLTS = "custom_numpy_volts"
DEFAULT_CUSTOM_NUMPY_VOLTS = [10.5, 11.58, 12.06, 13.6]
CONF_CUSTOM_NUMPY_PERCENT = "custom_numpy_percent"
DEFAULT_CUSTOM_NUMPY_PERCENT = [0, 20, 50, 100]

GATT_TIMEOUT = 20

BM_NAMES = ["Battery Monitor", "Li Battery Monitor", "ZX-1689"]

RATE_LIMIT_MODES = [
    "never",
    "when_charging",
    "when_not_charging",
    "always",
]

BATTERY_TYPES = [
    "Automatic (via BM2)",
    "AGM",
    "Deep-cycle",
    "Lead-acid",
    "LiFePO4",
    "iTechworld 120X (LiFePO4)",
    "Lithium-ion",
    "Custom",
]

BATTERY_STATUS_LIST = {
    0: "critical",
    1: "low",
    2: "normal",
    4: "charging",
    8: "floating",
}
