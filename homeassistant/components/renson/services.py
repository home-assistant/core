"""Services for the Renson integration."""

from enum import StrEnum

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class RensonService(StrEnum):
    """Store keys for Renson services."""

    SET_TIMER_LEVEL = "set_timer_level"
    SET_BREEZE = "set_breeze"
    SET_POLLUTION_SETTINGS = "set_pollution_settings"


class RensonServiceArgument(StrEnum):
    """Store keys for Renson service arguments."""

    TIMER_LEVEL = "timer_level"
    MINUTES = "minutes"
    BREEZE_LEVEL = "breeze_level"
    TEMPERATURE = "temperature"
    ACTIVATE = "activate"
    DAY_POLLUTION_LEVEL = "day_pollution_level"
    NIGHT_POLLUTION_LEVEL = "night_pollution_level"
    HUMIDITY_CONTROL = "humidity_control"
    AIRQUALITY_CONTROL = "airquality_control"
    CO2_CONTROL = "co2_control"
    CO2_THRESHOLD = "co2_threshold"
    CO2_HYSTERESIS = "co2_hysteresis"


SET_TIMER_LEVEL_SCHEMA: VolDictType = {
    probatio.Required(RensonServiceArgument.TIMER_LEVEL): probatio.In(
        ["level1", "level2", "level3", "level4", "holiday", "breeze"]
    ),
    probatio.Required(RensonServiceArgument.MINUTES): cv.positive_int,
}
SET_BREEZE_SCHEMA: VolDictType = {
    probatio.Required(RensonServiceArgument.BREEZE_LEVEL): probatio.In(
        ["level1", "level2", "level3", "level4"]
    ),
    probatio.Required(RensonServiceArgument.TEMPERATURE): cv.positive_int,
    probatio.Required(RensonServiceArgument.ACTIVATE): bool,
}
SET_POLLUTION_SETTINGS_SCHEMA: VolDictType = {
    probatio.Required(RensonServiceArgument.DAY_POLLUTION_LEVEL): probatio.In(
        ["level1", "level2", "level3", "level4"]
    ),
    probatio.Required(RensonServiceArgument.NIGHT_POLLUTION_LEVEL): probatio.In(
        ["level1", "level2", "level3", "level4"]
    ),
    probatio.Optional(RensonServiceArgument.HUMIDITY_CONTROL, default=True): bool,
    probatio.Optional(RensonServiceArgument.AIRQUALITY_CONTROL, default=True): bool,
    probatio.Optional(RensonServiceArgument.CO2_CONTROL, default=True): bool,
    probatio.Optional(
        RensonServiceArgument.CO2_THRESHOLD, default=600
    ): cv.positive_int,
    probatio.Optional(
        RensonServiceArgument.CO2_HYSTERESIS, default=100
    ): cv.positive_int,
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Renson integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RensonService.SET_TIMER_LEVEL,
        entity_domain=FAN_DOMAIN,
        schema=SET_TIMER_LEVEL_SCHEMA,
        func="set_timer_level",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RensonService.SET_BREEZE,
        entity_domain=FAN_DOMAIN,
        schema=SET_BREEZE_SCHEMA,
        func="set_breeze",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        RensonService.SET_POLLUTION_SETTINGS,
        entity_domain=FAN_DOMAIN,
        schema=SET_POLLUTION_SETTINGS_SCHEMA,
        func="set_pollution_settings",
    )
