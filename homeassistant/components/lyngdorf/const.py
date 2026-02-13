"""Constants for the Lyngdorf integration."""

from lyngdorf.const import supported_models

from homeassistant.const import Platform

DOMAIN = "lyngdorf"
DEFAULT_DEVICE_NAME = "Lyngdorf"

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
]
CONF_SERIAL_NUMBER = "serial_number"

MANUFACTURER_LYNGDORF = "Lyngdorf"

SUPPORTED_MANUFACTURERS = [MANUFACTURER_LYNGDORF]

SUPPORTED_DEVICES = [
    {"manufacturer": model.manufacturer, "model": model.model_name}
    for model in supported_models()
]

CONF_MANUFACTURER = "manufacturer"
