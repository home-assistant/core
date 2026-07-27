"""Constants for the Open Thread Border Router integration."""

DOMAIN = "otbr"

DEFAULT_CHANNEL = 15

# Milliseconds, matching the units of the OpenThread border agent API.
# OT_BORDER_AGENT_DEFAULT_EPHEMERAL_KEY_TIMEOUT; the API caps it at 10 minutes.
EPHEMERAL_KEY_LIFETIME = 2 * 60 * 1000
