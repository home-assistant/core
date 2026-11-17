"""Constants for the Airzone integration."""

from typing import Final

from aioairzone.common import TemperatureUnit

from homeassistant.const import UnitOfTemperature

CONF_MQTT_TOPIC: Final = "mqtt_topic"
DOMAIN: Final = "airzone"
MANUFACTURER: Final = "Airzone"

AIOAIRZONE_DEVICE_TIMEOUT_SEC: Final = 10

TEMP_UNIT_LIB_TO_HASS: Final[dict[TemperatureUnit, str]] = {
    TemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
    TemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}
