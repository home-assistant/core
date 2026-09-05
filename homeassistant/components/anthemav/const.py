"""Constants for the Anthem A/V Receivers integration."""

ANTHEMAV_UPDATE_SIGNAL = "anthemav_update"

DEFAULT_NAME = "Anthem AV"
DEFAULT_PORT = 14999
DOMAIN = "anthemav"
MANUFACTURER = "Anthem"
DEVICE_TIMEOUT_SECONDS = 4.0
# anthemav.Connection.create() retries its initial connection attempt
# internally (with exponential backoff) and only returns once it succeeds,
# so it does not fail on its own when the receiver is unreachable. Bound it
# here instead of relying on Home Assistant's global bootstrap timeout,
# which would otherwise let one unreachable-at-boot receiver block startup
# for minutes and can collaterally cancel other integrations still setting
# up alongside it.
CONNECT_TIMEOUT_SECONDS = 10.0
