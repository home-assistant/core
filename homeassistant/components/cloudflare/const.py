"""Constants for Cloudflare."""

DOMAIN = "cloudflare"

# Legacy config key kept for migration
CONF_RECORDS = "records"

# New config key for domains list (comma-separated in flow, stored as list)
CONF_DOMAINS = "domains"

PLATFORMS: list[str] = ["switch", "sensor"]

# Defaults
DEFAULT_UPDATE_INTERVAL = 60  # in minutes

# Services
SERVICE_UPDATE_RECORDS = "update_records"
