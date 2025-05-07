"""Constants for the EnergyID integration."""

from typing import Final

DOMAIN: Final = "energyid"

CONF_PROVISIONING_KEY: Final = "provisioning_key"
CONF_PROVISIONING_SECRET: Final = "provisioning_secret"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_RECORD_NUMBER: Final = "record_number"
CONF_RECORD_NAME: Final = "record_name"
CONF_HA_ENTITY_ID: Final = "ha_entity_id"
CONF_ENERGYID_KEY: Final = "energyid_key"

DATA_CLIENT: Final = "client"
DATA_LISTENERS: Final = "listeners"
DATA_MAPPINGS: Final = "mappings"

SIGNAL_CONFIG_ENTRY_CHANGED = f"{DOMAIN}_config_entry_changed"

DEFAULT_UPLOAD_INTERVAL_SECONDS: Final = 60

LISTENER_TYPE_STATE = "state_change"
