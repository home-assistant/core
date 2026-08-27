"""Constants for the SmartyPlants integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "smartyplants"

DEFAULT_HOST: Final = "https://api.smartyplants.ai"

# Poll interval used as the baseline. Webhook pushes land in between and keep
# the data fresher than this without changing the fallback cadence. The
# backend caches each account's payload and answers unchanged polls with a
# 304, so a poll that finds nothing new is cheap.
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=1)

# Key prefix for plants that have no sensor attached. Sensor-backed devices are
# keyed by sensor id, so the prefix keeps the two namespaces apart.
PLANT_KEY_PREFIX: Final = "plant:"

# Setup states surfaced by the status entity. Anything other than OK means the
# readings are not usable yet and says what the user needs to do about it.
STATUS_OK: Final = "ok"
STATUS_NO_SENSOR: Final = "no_sensor"
STATUS_NO_PLANT: Final = "no_plant"
STATUS_WAITING: Final = "waiting_for_data"
STATUS_OFFLINE: Final = "offline"
STATUS_OUTDATED: Final = "outdated"

STATUS_OPTIONS: Final = [
    STATUS_OK,
    STATUS_NO_SENSOR,
    STATUS_NO_PLANT,
    STATUS_WAITING,
    STATUS_OFFLINE,
    STATUS_OUTDATED,
]

CONF_WEBHOOK_SECRET: Final = "webhook_secret"

SIGNATURE_HEADER: Final = "X-Smartyplants-Signature"

# Push events the integration understands. Only sensor_update is required:
# the others are optimisations that let additions and deletions show up
# immediately instead of waiting for the next poll, and the integration
# behaves correctly if the backend never sends them.
EVENT_SENSOR_UPDATE: Final = "sensor_update"
EVENT_SENSOR_ADDED: Final = "sensor_added"
EVENT_SENSOR_REMOVED: Final = "sensor_removed"

# Readings older than this are treated as unreliable: the sensor has not
# reported for long enough that its last values no longer describe the plant.
STALE_AFTER: Final = timedelta(hours=3)

MANUFACTURER: Final = "SmartyPlants"
MODEL: Final = "Plant Sensor"
PLANT_ONLY_MODEL: Final = "Plant (no sensor)"
