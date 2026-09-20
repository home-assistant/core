"""Support for the Hive services."""

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_ONOFF,
    ATTR_TIME_PERIOD,
    DOMAIN,
    SERVICE_BOOST_HEATING_OFF,
    SERVICE_BOOST_HEATING_ON,
    SERVICE_BOOST_HOT_WATER,
    WATER_HEATER_MODES,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Hive services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_BOOST_HEATING_ON,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(ATTR_TIME_PERIOD): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            probatio.Optional(ATTR_TEMPERATURE, default="25.0"): probatio.Coerce(float),
        },
        func="async_heating_boost_on",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_BOOST_HEATING_OFF,
        entity_domain=CLIMATE_DOMAIN,
        schema=None,
        func="async_heating_boost_off",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_BOOST_HOT_WATER,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Optional(ATTR_TIME_PERIOD, default="00:30:00"): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            probatio.Required(ATTR_ONOFF): probatio.In(WATER_HEATER_MODES),
        },
        func="async_hot_water_boost",
    )
