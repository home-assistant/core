"""Constants for Airzone MQTT integration."""

from typing import Final

from airzone_mqtt.common import TemperatureUnit

from homeassistant.const import UnitOfTemperature

DOMAIN: Final[str] = "airzone_mqtt"
MANUFACTURER: Final[str] = "Airzone"

CONF_MQTT_TOPIC = "mqtt_topic"

AIRZONE_TIMEOUT_SEC: Final[int] = 10

TEMP_UNIT_LIB_TO_HASS: Final[dict[TemperatureUnit, str]] = {
    TemperatureUnit.CELSIUS: UnitOfTemperature.CELSIUS,
    TemperatureUnit.FAHRENHEIT: UnitOfTemperature.FAHRENHEIT,
}
