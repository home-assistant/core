"""Constants for the sentry integration."""

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_DOMAIN
from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.geo_location import DOMAIN as GEO_LOCATION_DOMAIN
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.humidifier import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

DOMAIN = "sentry"

CONF_DSN = "dsn"
CONF_ENVIRONMENT = "environment"

ENTITY_COMPONENTS = [
    AIR_QUALITY_DOMAIN,
    ALARM_CONTROL_PANEL_DOMAIN,
    BINARY_SENSOR_DOMAIN,
    CALENDAR_DOMAIN,
    CAMERA_DOMAIN,
    CLIMATE_DOMAIN,
    COVER_DOMAIN,
    DEVICE_TRACKER_DOMAIN,
    FAN_DOMAIN,
    GEO_LOCATION_DOMAIN,
    GROUP_DOMAIN,
    HUMIDIFIER_DOMAIN,
    LIGHT_DOMAIN,
    LOCK_DOMAIN,
    MEDIA_PLAYER_DOMAIN,
    REMOTE_DOMAIN,
    SCENE_DOMAIN,
    SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    VACUUM_DOMAIN,
    WATER_HEATER_DOMAIN,
    WEATHER_DOMAIN,
]
