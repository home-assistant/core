"""Services for the Nexia/American Standard/Trane integration."""

from enum import StrEnum

from nexia.const import HOLD_PERMANENT, HOLD_RESUME_SCHEDULE
import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN


class NexiaService(StrEnum):
    """Store keys for Nexia services."""

    SET_AIRCLEANER_MODE = "set_aircleaner_mode"
    SET_HUMIDIFY_SETPOINT = "set_humidify_setpoint"
    SET_DEHUMIDIFY_SETPOINT = "set_dehumidify_setpoint"
    SET_HVAC_RUN_MODE = "set_hvac_run_mode"


class NexiaServiceArgument(StrEnum):
    """Store keys for Nexia service arguments."""

    AIRCLEANER_MODE = "aircleaner_mode"
    HUMIDITY = "humidity"
    RUN_MODE = "run_mode"
    HVAC_MODE = "hvac_mode"


SET_AIRCLEANER_SCHEMA: VolDictType = {
    probatio.Required(NexiaServiceArgument.AIRCLEANER_MODE): cv.string,
}
SET_HUMIDIFY_SCHEMA: VolDictType = {
    probatio.Required(NexiaServiceArgument.HUMIDITY): probatio.All(
        probatio.Coerce(int), probatio.Range(min=10, max=45)
    ),
}
SET_DEHUMIDIFY_SCHEMA: VolDictType = {
    probatio.Required(NexiaServiceArgument.HUMIDITY): probatio.All(
        probatio.Coerce(int), probatio.Range(min=35, max=65)
    ),
}
SET_HVAC_RUN_MODE_SCHEMA = probatio.All(
    probatio.AtLeastOne(NexiaServiceArgument.RUN_MODE, NexiaServiceArgument.HVAC_MODE),
    cv.make_entity_service_schema(
        {
            probatio.Optional(NexiaServiceArgument.RUN_MODE): probatio.In(
                [HOLD_PERMANENT, HOLD_RESUME_SCHEDULE]
            ),
            probatio.Optional(NexiaServiceArgument.HVAC_MODE): probatio.In(
                [HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
            ),
        }
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Nexia/American Standard/Trane integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NexiaService.SET_HUMIDIFY_SETPOINT,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_HUMIDIFY_SCHEMA,
        func="async_set_humidify_setpoint",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NexiaService.SET_DEHUMIDIFY_SETPOINT,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_DEHUMIDIFY_SCHEMA,
        func="async_set_dehumidify_setpoint",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NexiaService.SET_AIRCLEANER_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_AIRCLEANER_SCHEMA,
        func="async_set_aircleaner_mode",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NexiaService.SET_HVAC_RUN_MODE,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_HVAC_RUN_MODE_SCHEMA,
        func="async_set_hvac_run_mode",
    )
