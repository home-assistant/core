"""Define constants for the Point component."""
from datetime import timedelta

DOMAIN = "point"

SCAN_INTERVAL = timedelta(minutes=1)

CONF_WEBHOOK_URL = "webhook_url"
EVENT_RECEIVED = "point_webhook_received"
SIGNAL_UPDATE_ENTITY = "point_update"
SIGNAL_WEBHOOK = "point_webhook"

POINT_DISCOVERY_NEW = "point_new_{}_{}"
