"""Services for the OSO Energy integration."""

import probatio

from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_DURATION_DAYS = "duration_days"
ATTR_UNTIL_TEMP_LIMIT = "until_temp_limit"
ATTR_V40MIN = "v40_min"
SERVICE_GET_PROFILE = "get_profile"
SERVICE_SET_PROFILE = "set_profile"
SERVICE_SET_V40MIN = "set_v40_min"
SERVICE_TURN_AWAY_MODE_ON = "turn_away_mode_on"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the OSO Energy integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_PROFILE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={},
        func="async_get_profile",
        supports_response=SupportsResponse.ONLY,
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TURN_AWAY_MODE_ON,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Required(ATTR_DURATION_DAYS): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=365)
            ),
        },
        func="async_oso_turn_away_mode_on",
    )

    service_set_profile_schema = cv.make_entity_service_schema(
        {
            probatio.Optional(f"hour_{hour:02d}"): probatio.All(
                probatio.Coerce(int), probatio.Range(min=10, max=75)
            )
            for hour in range(24)
        }
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_PROFILE,
        entity_domain=WATER_HEATER_DOMAIN,
        schema=service_set_profile_schema,
        func="async_set_profile",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_V40MIN,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={
            probatio.Required(ATTR_V40MIN): probatio.All(
                probatio.Coerce(float), probatio.Range(min=200, max=550)
            ),
        },
        func="async_set_v40_min",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TURN_OFF,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={probatio.Required(ATTR_UNTIL_TEMP_LIMIT): probatio.All(cv.boolean)},
        func="async_oso_turn_off",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TURN_ON,
        entity_domain=WATER_HEATER_DOMAIN,
        schema={probatio.Required(ATTR_UNTIL_TEMP_LIMIT): probatio.All(cv.boolean)},
        func="async_oso_turn_on",
    )
