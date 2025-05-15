"""Constants for the Autoskope integration."""

from datetime import timedelta

DOMAIN = "autoskope"

DEFAULT_HOST = "https://portal.autoskope.de"
UPDATE_INTERVAL = timedelta(seconds=60)

# Device information
MANUFACTURER = "Autoskope GmbH"

APP_VERSION = "2.40"

# Device types mapping
DEVICE_TYPE_MODELS = {
    "1": "AutoskopeX",
    "3": "Autoskope V2",
    "5": "Autoskope V2",
    "7": "Motoskope",
    "8": "Bootskope",
    "10": "Autoskope V3",
    "11": "Solarskope",
}
DEFAULT_MODEL = "Autoskope"  # Used as fallback model name
