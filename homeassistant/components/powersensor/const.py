"""Constants for the Powersensor integration."""

DOMAIN = "powersensor"
DEFAULT_NAME = "Powersensor"
DEFAULT_PORT = 49476
DEFAULT_SCAN_INTERVAL = 30

# Internal signals
CREATE_PLUG_SIGNAL = f"{DOMAIN}_create_plug"
CREATE_SENSOR_SIGNAL = f"{DOMAIN}_create_sensor"
DATA_UPDATE_SIGNAL_FMT_MAC_EVENT = f"{DOMAIN}_data_update_%s_%s"
ROLE_UPDATE_SIGNAL = f"{DOMAIN}_update_role"
PLUG_ADDED_TO_HA_SIGNAL = f"{DOMAIN}_plug_added_to_homeassistant"
SENSOR_ADDED_TO_HA_SIGNAL = f"{DOMAIN}_sensor_added_to_homeassistant"
UPDATE_VHH_SIGNAL = f"{DOMAIN}_update_vhh"
ZEROCONF_ADD_PLUG_SIGNAL = f"{DOMAIN}_zeroconf_add_plug"
ZEROCONF_REMOVE_PLUG_SIGNAL = f"{DOMAIN}_zeroconf_remove_plug"
ZEROCONF_UPDATE_PLUG_SIGNAL = f"{DOMAIN}_zeroconf_update_plug"

# Formatting, would've liked to have been able to have this translatable
SENSOR_NAME_FORMAT = "Powersensor Sensor (ID: %s) ⚡"

# Config entry keys
CFG_DEVICES = "devices"
CFG_ROLES = "roles"

# Role names (fixed, as-received from plug API)
ROLE_APPLIANCE = "appliance"
ROLE_HOUSENET = "house-net"
ROLE_SOLAR = "solar"
ROLE_WATER = "water"

# runtime_data keys
RT_DISPATCHER = "dispatcher"
RT_VHH = "vhh"
RT_VHH_LOCK = "vhh_update_lock"
RT_VHH_MAINS_ADDED = "vhh_main_added"
RT_VHH_SOLAR_ADDED = "vhh_solar_added"
RT_ZEROCONF = "zeroconf"
