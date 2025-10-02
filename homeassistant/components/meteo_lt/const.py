"""Constants for the Meteo.lt integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "meteo_lt"
PLATFORMS = [Platform.WEATHER]

MANUFACTURER = "Lithuanian Hydrometeorological Service"
MODEL = "Weather Station"

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=30)

CONF_PLACE_CODE = "place_code"

ATTRIBUTION = "Data provided by Lithuanian Hydrometeorological Service (LHMT)"
