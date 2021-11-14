"""Constants for the Homewizard Energy integration."""

# Set up.
DOMAIN = "homewizard_energy"
COORDINATOR = "coordinator"
MANUFACTURER_NAME = "HomeWizard"
PLATFORMS = ["sensor", "switch"]

# Platform config.
CONF_SERIAL = "serial"
CONF_API = "api"
CONF_MODEL = "model"
CONF_SW_VERSION = "sw_ver"
CONF_DATA = "data"

# Service attributes.
ATTR_ACTIVE_POWER_L1_W = "active_power_l1_w"
ATTR_ACTIVE_POWER_L2_W = "active_power_l2_w"
ATTR_ACTIVE_POWER_L3_W = "active_power_l3_w"
ATTR_ACTIVE_POWER_W = "active_power_w"
ATTR_GAS_TIMESTAMP = "gas_timestamp"
ATTR_METER_MODEL = "meter_model"
ATTR_SMR_VERSION = "smr_version"
ATTR_TOTAL_ENERGY_EXPORT_T1_KWH = "total_power_export_t1_kwh"
ATTR_TOTAL_ENERGY_EXPORT_T2_KWH = "total_power_export_t2_kwh"
ATTR_TOTAL_ENERGY_IMPORT_T1_KWH = "total_power_import_t1_kwh"
ATTR_TOTAL_ENERGY_IMPORT_T2_KWH = "total_power_import_t2_kwh"
ATTR_TOTAL_GAS_M3 = "total_gas_m3"
ATTR_WIFI_SSID = "wifi_ssid"
ATTR_WIFI_STRENGTH = "wifi_strength"

# State attributes
ATTR_POWER_ON = "power_on"
ATTR_SWITCHLOCK = "switch_lock"
ATTR_BRIGHTNESS = "brightness"

# Default values.
DEFAULT_STR_VALUE = "undefined"
DEVICE_DEFAULT_NAME = "P1 Meter"

# Device models
MODEL_P1 = "HWE-P1"
MODEL_KWH_1 = "SDM230-wifi"
MODEL_KWH_3 = "SDM630-wifi"
MODEL_SOCKET = "HWE-SKT"
