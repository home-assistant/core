"""Constants for the HomematicIP Cloud component."""
import logging

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

_LOGGER = logging.getLogger(".")

DOMAIN = "homematicip_cloud"

PLATFORMS = [
    ALARM_CONTROL_PANEL_DOMAIN,
    BINARY_SENSOR_DOMAIN,
    CLIMATE_DOMAIN,
    COVER_DOMAIN,
    LIGHT_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    WEATHER_DOMAIN,
]

CONF_ACCESSPOINT = "accesspoint"
CONF_AUTHTOKEN = "authtoken"

HMIPC_NAME = "name"
HMIPC_HAPID = "hapid"
HMIPC_AUTHTOKEN = "authtoken"
HMIPC_PIN = "pin"
