"""Constants for the Anthem A/V Receivers integration."""

ANTHEMAV_UPDATE_SIGNAL = "anthemav_update"

DEFAULT_NAME = "Anthem AV"
DEFAULT_PORT = 14999
DOMAIN = "anthemav"
MANUFACTURER = "Anthem"
DEVICE_TIMEOUT_SECONDS = 4.0
# anthemav.Connection.create() retries internally and only returns once
# connected, so it never fails on its own when the receiver is unreachable.
CONNECT_TIMEOUT_SECONDS = 10.0
