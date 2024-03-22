"""Constants for the Arctic Spa integration."""

DOMAIN = "arcticspa"

# How often shall we poll for status on the remote endpoint. (in seconds)
UPDATE_INTERVAL = 15

# How long to wait for a change to set (stop bouncing) before a new status request is sent.
REQUEST_REFRESH_COOLDOWN = 0.8
