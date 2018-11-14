"""Define constants for the Point component."""
from datetime import timedelta

DOMAIN = 'point'
CLIENT_ID = 'client_id'
CLIENT_SECRET = 'client_secret'


SCAN_INTERVAL = timedelta(minutes=1)

CONF_WEBHOOK_URL = 'webhook_url'
EVENT_RECEIVED = 'point_webhook_received'
SIGNAL_UPDATE_ENTITY = 'point_update'
SIGNAL_WEBHOOK = 'point_webhook'
NEW_DEVICE = 'new_device'
