"""Services for the OSO Energy integration."""

from enum import StrEnum

import probatio

from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class OSOEnergyService(StrEnum):
    """Store keys for OSO Energy services."""

    GET_PROFILE = "get_profile"
    SET_PROFILE = "set_profile"
    SET_V40_MIN = "set_v40_min"
    TURN_AWAY_MODE_ON = "turn_away_mode_on"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"


class OSOEnergyServiceArgument(StrEnum):
    """Store keys for OSO Energy service arguments."""

    HOUR_00 = "hour_00"
    HOUR_01 = "hour_01"
    HOUR_02 = "hour_02"
    HOUR_03 = "hour_03"
    HOUR_04 = "hour_04"
    HOUR_05 = "hour_05"
    HOUR_06 = "hour_06"
    HOUR_07 = "hour_07"
    HOUR_08 = "hour_08"
    HOUR_09 = "hour_09"
    HOUR_10 = "hour_10"
    HOUR_11 = "hour_11"
    HOUR_12 = "hour_12"
    HOUR_13 = "hour_13"
    HOUR_14 = "hour_14"
    HOUR_15 = "hour_15"
    HOUR_16 = "hour_16"
    HOUR_17 = "hour_17"
    HOUR_18 = "hour_18"
    HOUR_19 = "hour_19"
    HOUR_20 = "hour_20"
    HOUR_21 = "hour_21"
    HOUR_22 = "hour_22"
    HOUR_23 = "hour_23"
    V40_MIN = "v40_min"
    DURATION_DAYS = "duration_days"
    UNTIL_TEMP_LIMIT = "until_temp_limit"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the OSO Energy integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OSOEnergyService.GET_PROFILE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={},
        func="async_get_profile",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OSOEnergyService.TURN_AWAY_MODE_ON,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Required(OSOEnergyServiceArgument.DURATION_DAYS): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=365)
            ),
        },
        func="async_oso_turn_away_mode_on",
    )

    service_set_profile_schema = cv.make_entity_service_schema(
        {
            probatio.Optional(
                OSOEnergyServiceArgument[f"HOUR_{hour:02d}"]
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=10, max=75))
            for hour in range(24)
        }
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OSOEnergyService.SET_PROFILE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema=service_set_profile_schema,
        func="async_set_profile",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OSOEnergyService.SET_V40_MIN,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Required(OSOEnergyServiceArgument.V40_MIN): probatio.All(
                probatio.Coerce(float), probatio.Range(min=200, max=550)
            ),
        },
        func="async_set_v40_min",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OSOEnergyService.TURN_OFF,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Required(OSOEnergyServiceArgument.UNTIL_TEMP_LIMIT): probatio.All(
                cv.boolean
            )
        },
        func="async_oso_turn_off",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        OSOEnergyService.TURN_ON,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Required(OSOEnergyServiceArgument.UNTIL_TEMP_LIMIT): probatio.All(
                cv.boolean
            )
        },
        func="async_oso_turn_on",
    )
