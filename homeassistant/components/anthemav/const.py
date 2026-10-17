"""Constants for the Anthem A/V Receivers integration."""

from datetime import timedelta

ANTHEMAV_UPDATE_SIGNAL = "anthemav_update"

DEFAULT_NAME = "Anthem AV"
DEFAULT_PORT = 14999
DOMAIN = "anthemav"
MANUFACTURER = "Anthem"
DEVICE_TIMEOUT_SECONDS = 4.0

# MRX x10 receivers don't push volume changes, so poll their zone state.
POLL_MODELS = ("MRX 310", "MRX 510", "MRX 710")
POLL_INTERVAL = timedelta(seconds=5)
