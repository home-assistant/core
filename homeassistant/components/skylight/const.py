"""Constants for the Skylight integration."""

from datetime import timedelta

DOMAIN = "skylight"

CONF_DEVICE_FINGERPRINT = "device_fingerprint"
CONF_FRAME_ID = "frame_id"
CONF_FRAME_NAME = "frame_name"
CONF_REFRESH_TOKEN = "refresh_token"

# Rolling event window fetched on every poll (Skylight works in whole days).
EVENTS_PAST_DAYS = 14
EVENTS_FUTURE_DAYS = 60

UPDATE_INTERVAL = timedelta(minutes=5)
