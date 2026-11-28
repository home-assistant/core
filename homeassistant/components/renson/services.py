"""Services for the Renson integration."""

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN

SET_TIMER_LEVEL_SCHEMA: VolDictType = {
    probatio.Required("timer_level"): probatio.In(
        ["level1", "level2", "level3", "level4", "holiday", "breeze"]
    ),
    probatio.Required("minutes"): cv.positive_int,
}
SET_BREEZE_SCHEMA: VolDictType = {
    probatio.Required("breeze_level"): probatio.In(
        ["level1", "level2", "level3", "level4"]
    ),
    probatio.Required("temperature"): cv.positive_int,
    probatio.Required("activate"): bool,
}
SET_POLLUTION_SETTINGS_SCHEMA: VolDictType = {
    probatio.Required("day_pollution_level"): probatio.In(
        ["level1", "level2", "level3", "level4"]
    ),
    probatio.Required("night_pollution_level"): probatio.In(
        ["level1", "level2", "level3", "level4"]
    ),
    probatio.Optional("humidity_control", default=True): bool,
    probatio.Optional("airquality_control", default=True): bool,
    probatio.Optional("co2_control", default=True): bool,
    probatio.Optional("co2_threshold", default=600): cv.positive_int,
    probatio.Optional("co2_hysteresis", default=100): cv.positive_int,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Renson integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_timer_level",
        entity_domain=FAN_DOMAIN,
        schema=SET_TIMER_LEVEL_SCHEMA,
        func="set_timer_level",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_breeze",
        entity_domain=FAN_DOMAIN,
        schema=SET_BREEZE_SCHEMA,
        func="set_breeze",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_pollution_settings",
        entity_domain=FAN_DOMAIN,
        schema=SET_POLLUTION_SETTINGS_SCHEMA,
        func="set_pollution_settings",
    )
