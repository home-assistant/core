"""Constants for the Arctic Spa integration."""

DOMAIN = "arcticspa"

CONF_ARCTIC_SPA_KEY_NAME = "Hot Tub API Key"

# How often shall we poll for status on the remote endpoint.
# The ArcticSpas remote endpoint has a very low tolerance for regular polling. (About 15 poll per minute.)
# Home Assistant can easily overload this to provide a usable UI for the user.
# If the number is set lower, the API will limit polling with a 429: Too Many Requests error, causing the
# user interface to lock up ("unavailable") until the limit is lifted. (Which can take a few seconds.)
# If the number is set higher, the user interface get notified of the change too late, causing transient switching.
REQUEST_REFRESH_DELAY = 4
