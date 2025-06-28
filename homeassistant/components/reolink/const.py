"""Constants for the Reolink Camera integration."""

DOMAIN = "reolink"

CONF_USE_HTTPS = "use_https"
CONF_BC_PORT = "baichuan_port"
CONF_BC_ONLY = "baichuan_only"
CONF_SUPPORTS_PRIVACY_MODE = "privacy_mode_supported"

# Conserve battery by not waking the battery cameras each minute during normal update
# Most props are cached in the Home Hub and updated, but some are skipped
BATTERY_PASSIVE_WAKE_UPDATE_INTERVAL = 3600  # seconds
BATTERY_WAKE_UPDATE_INTERVAL = 6 * BATTERY_PASSIVE_WAKE_UPDATE_INTERVAL
BATTERY_ALL_WAKE_UPDATE_INTERVAL = 2 * BATTERY_WAKE_UPDATE_INTERVAL
