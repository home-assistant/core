"""Constants for Cloudflare."""

DOMAIN = "cloudflare"

# Legacy config key kept for migration
CONF_RECORDS = "records"

# New config key for list of domains (stored as list[str] from flow)
CONF_DOMAINS = "domains"

PLATFORMS: list[str] = ["sensor", "switch"]

# Defaults
DEFAULT_UPDATE_INTERVAL = 60  # in minutes

# Services
SERVICE_UPDATE_RECORDS = "update_records"
