"""Constants for the Meross Bluetooth integration."""

from __future__ import annotations

from logging import Logger, getLogger

DOMAIN = "meross"
MANUFACTURER = "Meross"
LOGGER: Logger = getLogger(__package__)

CONF_MODEL = "model"
CONF_RETRY_COUNT = "retry_count"
CONF_BOUND_IDENTIFY_DONE = "bound_identify_done"

# MS120 history progress stored on the config entry.
CONF_TEMP_HISTORY_NEXT_IDX = "temp_history_next_idx"
CONF_HUMI_HISTORY_NEXT_IDX = "humidity_history_next_idx"
CONF_TEMP_HISTORY_LAST_TS = "temp_history_last_ts"
CONF_HUMI_HISTORY_LAST_TS = "humidity_history_last_ts"

DEVICE_STARTUP_TIMEOUT = 30
# Local watchdog: mark unavailable if no parseable advertisement.
# Needed on macOS where Bleak's discovered cache often never expires, so HA's
# async_track_unavailable may never fire after battery removal / BT off.
ADVERTISEMENT_STALE_SECONDS = 600
# Shared across all Meross BLE entries: Pi/USB adapters often have 1 connection slot.
DATA_BLE_GATT_LOCK = "ble_gatt_lock"

USER_SETUP_MODELS = ("ms120", "ms220", "ms420", "ms700")
MANUAL_SCAN_DURATION = 15
