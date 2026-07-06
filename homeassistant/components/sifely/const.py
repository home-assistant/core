"""HA-specific constants for the Sifely smart lock integration.

API constants (lock states, passcode types, endpoints) live in the
pysifely package; only Home Assistant integration constants belong here.
"""

# Integration domain
DOMAIN = "sifely"

# Polling interval (seconds)
DEFAULT_SCAN_INTERVAL = 300

# OAuth client identifier sent to the Sifely API
DEFAULT_CLIENT_ID = "home_assistant"

# Config entry data keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_CLIENT_ID = "client_id"
CONF_BASE_URL = "base_url"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
