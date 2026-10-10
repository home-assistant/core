"""Constants for the Redfish integration."""

from datetime import timedelta

DOMAIN = "redfish"
CONF_BASE_URL = "base_url"
DEFAULT_VERIFY_SSL = True
UPDATE_INTERVAL = timedelta(minutes=1)
REQUEST_TIMEOUT = 10
COLLECTION_TIMEOUT = 60
