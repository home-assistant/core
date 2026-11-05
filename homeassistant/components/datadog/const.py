"""Constants for the Datadog integration."""

from datetime import timedelta

DOMAIN = "datadog"

CONF_RATE = "rate"
CONF_RESEND_UNCHANGED = "resend_unchanged"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8125
DEFAULT_PREFIX = "hass"
DEFAULT_RATE = 1
DEFAULT_RESEND_UNCHANGED = False

SEND_INTERVAL = timedelta(seconds=60)
