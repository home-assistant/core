"""Constants for the Lyngdorf integration."""

from lyngdorf.const import supported_models

from homeassistant.const import Platform

DOMAIN = "lyngdorf"
DEFAULT_DEVICE_NAME = "Lyngdorf MP-60"

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]
CONF_SERIAL_NUMBER = "serial_number"

MANUFACTURER_LYNGDORF = "Lyngdorf"

SUPPORTED_MANUFACTURERS = [MANUFACTURER_LYNGDORF]  # Steinway todo

SUPPORTED_DEVICES = [
    {"manufacturer": model.manufacturer, "model": model.model_name}
    for model in supported_models()
]

CONF_MANUFACTURER = "manufacturer"
