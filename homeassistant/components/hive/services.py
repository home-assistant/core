"""Services for the Hive integration."""

from enum import StrEnum

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN, WATER_HEATER_MODES


class HiveService(StrEnum):
    """Store keys for Hive services."""

    BOOST_HEATING_ON = "boost_heating_on"
    BOOST_HEATING_OFF = "boost_heating_off"
    BOOST_HOT_WATER = "boost_hot_water"


class HiveServiceArgument(StrEnum):
    """Store keys for Hive service arguments."""

    TIME_PERIOD = "time_period"
    TEMPERATURE = "temperature"
    ON_OFF = "on_off"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Hive integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HiveService.BOOST_HEATING_ON,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(HiveServiceArgument.TIME_PERIOD): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            probatio.Optional(
                HiveServiceArgument.TEMPERATURE, default="25.0"
            ): probatio.Coerce(float),
        },
        func="async_heating_boost_on",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HiveService.BOOST_HEATING_OFF,
        entity_domain=CLIMATE_DOMAIN,
        schema=None,
        func="async_heating_boost_off",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        HiveService.BOOST_HOT_WATER,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Optional(
                HiveServiceArgument.TIME_PERIOD, default="00:30:00"
            ): probatio.All(
                cv.time_period,
                cv.positive_timedelta,
                lambda td: td.total_seconds() // 60,
            ),
            probatio.Required(HiveServiceArgument.ON_OFF): probatio.In(
                WATER_HEATER_MODES
            ),
        },
        func="async_hot_water_boost",
    )
