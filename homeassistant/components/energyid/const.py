"""Constants for the EnergyID integration."""

from typing import Final

DOMAIN: Final = "energyid"

# --- Config Flow and Entry Data ---
CONF_PROVISIONING_KEY: Final = "provisioning_key"
CONF_PROVISIONING_SECRET: Final = "provisioning_secret"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"

# --- Subentry (Mapping) Data ---
CONF_HA_ENTITY_ID: Final = "ha_entity_id"
CONF_ENERGYID_KEY: Final = "energyid_key"

# --- Data stored in hass.data ---
DATA_CLIENT: Final = "client"
DATA_LISTENERS: Final = "listeners"
DATA_MAPPINGS: Final = "mappings"


# --- Signals for dispatcher ---
SIGNAL_CONFIG_ENTRY_CHANGED = f"{DOMAIN}_config_entry_changed"

# --- Defaults ---
DEFAULT_UPLOAD_INTERVAL_SECONDS: Final = 60
