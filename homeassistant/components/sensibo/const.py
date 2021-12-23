"""Constants for Sensibo."""

DOMAIN = "sensibo"
PLATFORMS = ["climate"]
ALL = ["all"]
DEFAULT_NAME = "Sensibo@Home"
TIMEOUT = 8
_FETCH_FIELDS = ",".join(
    [
        "room{name}",
        "measurements",
        "remoteCapabilities",
        "acState",
        "connectionStatus{isAlive}",
        "temperatureUnit",
    ]
)
_INITIAL_FETCH_FIELDS = f"id,firmwareVersion,firmwareType,productModel,{_FETCH_FIELDS}"
