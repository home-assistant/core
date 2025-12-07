"""Constants for the EnergyID integration."""

from typing import Final

DOMAIN: Final = "energyid"
NAME: Final = "EnergyID"

# --- Config Flow and Entry Data ---
CONF_PROVISIONING_KEY: Final = "provisioning_key"
CONF_PROVISIONING_SECRET: Final = "provisioning_secret"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"

# --- Subentry (Mapping) Data ---
CONF_HA_ENTITY_UUID: Final = "ha_entity_uuid"
CONF_ENERGYID_KEY: Final = "energyid_key"

# --- Webhook and Polling Configuration ---
ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX: Final = "homeassistant_eid_"
POLLING_INTERVAL: Final = 2  # seconds
MAX_POLLING_ATTEMPTS: Final = 60  # 2 minutes total
