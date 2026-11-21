"""Constants for the Anthem A/V Receivers integration."""

from datetime import timedelta

ANTHEMAV_UPDATE_SIGNAL = "anthemav_update"

DEFAULT_NAME = "Anthem AV"
DEFAULT_PORT = 14999
DOMAIN = "anthemav"
MANUFACTURER = "Anthem"
DEVICE_TIMEOUT_SECONDS = 4.0

# MRX x10 receivers don't push volume changes, so poll their zone state.
# They also often ignore input changes sent over the long-lived connection,
# but act on them when sent over a new connection.
X10_MODELS = ("MRX 310", "MRX 510", "MRX 710")
POLL_INTERVAL = timedelta(seconds=5)
# The receiver answers "!I" to queries sent back to back; the library's own
# refresh waits 20 ms between them.
POLL_COMMAND_SPACING_SECONDS = 0.02
# The library names listening modes from the x20 table; x10 receivers use
# the same numbers, other series don't.
SOUND_MODE_MODELS = (*X10_MODELS, "MRX 520", "MRX 720", "MRX 1120", "AVM 60")
SINGLE_COMMAND_TIMEOUT_SECONDS = 5.0
# Keep the connection open briefly after sending, so the receiver acts on the
# command before the socket closes.
SINGLE_COMMAND_LINGER_SECONDS = 1.0
