"""Constants for the Meraki Dashboard integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "meraki_dashboard"

CONF_NETWORK_ID: Final = "network_id"
CONF_NETWORK_NAME: Final = "network_name"
CONF_ORGANIZATION_ID: Final = "organization_id"

DEFAULT_BASE_URL: Final = "https://api.meraki.com/api/v1"
DEFAULT_TIMESPAN_SECONDS: Final = 300
DEFAULT_PER_PAGE: Final = 5000
UPDATE_INTERVAL: Final = timedelta(minutes=5)

CONF_TRACK_CLIENTS: Final = "track_clients"
CONF_TRACK_BLUETOOTH_CLIENTS: Final = "track_bluetooth_clients"
CONF_TRACK_INFRASTRUCTURE_DEVICES: Final = "track_infrastructure_devices"
CONF_INCLUDED_CLIENTS: Final = "included_clients"

DEFAULT_TRACK_CLIENTS: Final = True
DEFAULT_TRACK_BLUETOOTH_CLIENTS: Final = False
DEFAULT_TRACK_INFRASTRUCTURE_DEVICES: Final = True
