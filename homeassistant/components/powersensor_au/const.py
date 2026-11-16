"""Constants for the Powersensor integration."""

DOMAIN = "powersensor_au"

CREATE_PLUG_SIGNAL = f"{DOMAIN}_create_plug"
CREATE_SENSOR_SIGNAL = f"{DOMAIN}_create_sensor"
DATA_UPDATE_SIGNAL_PREFIX = f"{DOMAIN}_data_update_"
DEVICE_REMOVED_SIGNAL = f"{DOMAIN}_device_removed"
ROLE_UPDATE_SIGNAL = f"{DOMAIN}_update_role"
UPDATE_VHH_SIGNAL = f"{DOMAIN}_update_vhh"

CFG_ROLES = "roles"

# Device registry identifier of the household view device.
VHH_DEVICE_ID = "vhh"

# Role names (fixed, as-received from plug API)
ROLE_APPLIANCE = "appliance"
ROLE_HOUSENET = "house-net"
ROLE_SOLAR = "solar"
ROLE_UNKNOWN = "unknown"
ROLE_WATER = "water"
