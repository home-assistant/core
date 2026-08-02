"""Constants for the Redfish integration."""

from datetime import timedelta

DOMAIN = "redfish"
CONF_BASE_URL = "base_url"
DEFAULT_VERIFY_SSL = False
UPDATE_INTERVAL = timedelta(minutes=1)
REQUEST_TIMEOUT = 10
