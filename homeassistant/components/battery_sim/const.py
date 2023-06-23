"""Constants for the battery_sim component."""

DOMAIN = "battery_sim"

BATTERY_TYPE = "battery"

BATTERY_PLATFORMS = ["sensor", "switch", "button"]

DATA_UTILITY = "battery_sim_data"

SETUP_TYPE = "setup_type"
CONFIG_FLOW = "config_flow"
YAML = "yaml"

CONF_BATTERY = "battery"
CONF_IMPORT_SENSOR = "import_sensor"
CONF_SECOND_IMPORT_SENSOR = "second_import_sensor"
CONF_EXPORT_SENSOR = "export_sensor"
CONF_SECOND_EXPORT_SENSOR = "second_export_sensor"
CONF_BATTERY_SIZE = "size_kwh"
CONF_BATTERY_MAX_DISCHARGE_RATE = "max_discharge_rate_kw"
CONF_BATTERY_MAX_CHARGE_RATE = "max_charge_rate_kw"
CONF_BATTERY_EFFICIENCY = "efficiency"
CONF_ENERGY_TARIFF = "energy_tariff"
CONF_ENERGY_IMPORT_TARIFF = "energy_import_tariff"
CONF_ENERGY_EXPORT_TARIFF = "energy_export_tariff"
CONF_UNIQUE_NAME = "unique_name"
ATTR_VALUE = "value"
METER_TYPE = "type_of_energy_meter"
ONE_IMPORT_ONE_EXPORT_METER = "one_import_one_export"
TWO_IMPORT_ONE_EXPORT_METER = "two_import_one_export"
TWO_IMPORT_TWO_EXPORT_METER = "two_import_two_export"
TARIFF_TYPE = "tariff_type"
NO_TARIFF_INFO = "No tariff information"
TARIFF_SENSOR_ENTITIES = "Sensors that track tariffs"
FIXED_NUMERICAL_TARIFFS = "Fixed value for tariffs"

ATTR_SOURCE_ID = "source"
ATTR_STATUS = "status"
PRECISION = 3
ATTR_ENERGY_SAVED = "total energy saved"
ATTR_ENERGY_SAVED_TODAY = "energy_saved_today"
ATTR_ENERGY_SAVED_WEEK = "energy_saved_this_week"
ATTR_ENERGY_SAVED_MONTH = "energy_saved_this_month"
ATTR_DATE_RECORDING_STARTED = "date_recording_started"
ATTR_ENERGY_BATTERY_OUT = "battery_energy_out"
ATTR_ENERGY_BATTERY_IN = "battery_energy_in"
ATTR_MONEY_SAVED = "total_money_saved"
ATTR_MONEY_SAVED_IMPORT = "money_saved_on_imports"
ATTR_MONEY_SAVED_EXPORT = "extra_money_earned_on_exports"
CHARGING_RATE = "current charging rate"
DISCHARGING_RATE = "current discharging rate"
ATTR_CHARGE_PERCENTAGE = "percentage"
GRID_EXPORT_SIM = "simulated grid export after battery charging"
GRID_IMPORT_SIM = "simulated grid import after battery discharging"
ICON_CHARGING = "mdi:battery-charging-50"
ICON_DISCHARGING = "mdi:battery-50"
ICON_FULL = "mdi:battery"
ICON_EMPTY = "mdi:battery-outline"
OVERIDE_CHARGING = "force_charge"
FORCE_DISCHARGE = "force_discharge"
CHARGE_ONLY = "charge_only"
PAUSE_BATTERY = "pause_battery"
RESET_BATTERY = "reset_battery"
PERCENTAGE_ENERGY_IMPORT_SAVED = "percentage_import_energy_saved"
BATTERY_CYCLES = "battery_cycles"

BATTERY_MODE = "Battery_mode_now"
MODE_IDLE = "Idle/Paused"
MODE_CHARGING = "Charging"
MODE_DISCHARGING = "Discharging"
MODE_FORCE_CHARGING = "Forced charging"
MODE_FORCE_DISCHARGING = "Forced discharging"
MODE_FULL = "Full"
MODE_EMPTY = "Empty"

BATTERY_OPTIONS = {
    "Tesla Powerwall": {
        CONF_BATTERY_SIZE: 13.5,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.0,
        CONF_BATTERY_MAX_CHARGE_RATE: 3.68,
        CONF_BATTERY_EFFICIENCY: 0.9 },
    "LG Chem": {
        CONF_BATTERY_SIZE: 9.3,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 5.0,
        CONF_BATTERY_MAX_CHARGE_RATE: 3.3,
        CONF_BATTERY_EFFICIENCY: 0.95 },
    "Sonnen Eco": {
        CONF_BATTERY_SIZE: 5.0,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 2.5,
        CONF_BATTERY_MAX_CHARGE_RATE: 2.5,
        CONF_BATTERY_EFFICIENCY: 0.9},
    "Pika Harbour": {
        CONF_BATTERY_SIZE: 8.6,
        CONF_BATTERY_MAX_DISCHARGE_RATE: 4.2,
        CONF_BATTERY_MAX_CHARGE_RATE: 4.2,
        CONF_BATTERY_EFFICIENCY: 0.965},
    "Custom":{}
    }
