"""UpCloud constants."""

from datetime import timedelta

DOMAIN = "upcloud"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
CONFIG_ENTRY_UPDATE_SIGNAL_TEMPLATE = f"{DOMAIN}_config_entry_update:" "{}"
