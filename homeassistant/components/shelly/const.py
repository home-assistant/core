"""Constants for the Shelly integration."""

DATA_CONFIG_ENTRY = "config_entry"
DOMAIN = "shelly"

# Used to calculate the timeout in "_async_update_data" used for polling data from devices.
POLLING_TIMEOUT_MULTIPLIER = 1.2

# Timeout used for initial entry setup in "async_setup_entry".
SETUP_ENTRY_TIMEOUT_SEC = 10

# Multiplier used to calculate the "update_interval" for sleeping devices.
SLEEP_PERIOD_MULTIPLIER = 1.2

# Multiplier used to calculate the "update_interval" for non-sleeping devices.
UPDATE_PERIOD_MULTIPLIER = 2.2
