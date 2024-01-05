"""Constants for the Arctic Spa integration."""

DOMAIN = "arcticspa"

# How often shall we poll for status on the remote endpoint. (in seconds)
#
# The ArcticSpas remote endpoint has a low tolerance for regular polling.
# (About 15 requests per minute or "every 4 seconds".)
# It limits with a "429 Too Many Requests" error after a one-minute timeframe.
UPDATE_INTERVAL = 6.5

# How long to wait for a change to set (stop bouncing) before a new status request is sent.
REQUEST_REFRESH_COOLDOWN = 0.8
