"""Schemas for geniushub integration."""

from datetime import timedelta

import probatio

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

from .const import GeniusHubServiceArgument

CLOUD_API_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_TOKEN): str,
    }
)


LOCAL_API_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


SET_SWITCH_OVERRIDE_SCHEMA: VolDictType = {
    probatio.Optional(GeniusHubServiceArgument.DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
    ),
}
SET_ZONE_MODE_SCHEMA: VolDictType = {
    probatio.Required(GeniusHubServiceArgument.MODE): probatio.In(
        ["off", "timer", "footprint"]
    ),
}
SET_ZONE_MODE_SCHEMA_WATER_HEATER: VolDictType = {
    probatio.Required(GeniusHubServiceArgument.MODE): probatio.In(["off", "timer"]),
}
SET_ZONE_OVERRIDE_SCHEMA: VolDictType = {
    probatio.Required(GeniusHubServiceArgument.TEMPERATURE): probatio.All(
        probatio.Coerce(float), probatio.Range(min=4, max=28)
    ),
    probatio.Optional(GeniusHubServiceArgument.DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
    ),
}
SET_ZONE_OVERRIDE_HOT_WATER_SCHEMA: VolDictType = {
    probatio.Required(GeniusHubServiceArgument.TEMPERATURE): probatio.All(
        probatio.Coerce(float), probatio.Range(min=35, max=75)
    ),
    probatio.Optional(GeniusHubServiceArgument.DURATION): probatio.All(
        cv.time_period,
        probatio.Range(min=timedelta(minutes=5), max=timedelta(days=1)),
    ),
}
