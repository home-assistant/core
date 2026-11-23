"""Services for the SmartTub integration."""

import probatio
import smarttub

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, SmartTubService, SmartTubServiceArgument

RESET_REMINDER_SCHEMA: VolDictType = {
    probatio.Required(SmartTubServiceArgument.DAYS): probatio.All(
        probatio.Coerce(int), probatio.Range(min=30, max=365)
    )
}
SNOOZE_REMINDER_SCHEMA: VolDictType = {
    probatio.Required(SmartTubServiceArgument.DAYS): probatio.All(
        probatio.Coerce(int), probatio.Range(min=10, max=120)
    )
}
SET_PRIMARY_FILTRATION_SCHEMA = probatio.All(
    probatio.AtLeastOne(
        SmartTubServiceArgument.DURATION, SmartTubServiceArgument.START_HOUR
    ),
    cv.make_entity_service_schema(
        {
            probatio.Optional(SmartTubServiceArgument.DURATION): probatio.All(
                int, probatio.Range(min=1, max=24)
            ),
            probatio.Optional(SmartTubServiceArgument.START_HOUR): probatio.All(
                int, probatio.Range(min=0, max=23)
            ),
        },
    ),
)
SET_SECONDARY_FILTRATION_SCHEMA: VolDictType = {
    probatio.Required(SmartTubServiceArgument.MODE): probatio.In(
        {
            mode.name.lower()
            for mode in smarttub.SpaSecondaryFiltrationCycle.SecondaryFiltrationMode
        }
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the SmartTub integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SmartTubService.SNOOZE_REMINDER,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=SNOOZE_REMINDER_SCHEMA,
        func="async_snooze",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SmartTubService.RESET_REMINDER,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=RESET_REMINDER_SCHEMA,
        func="async_reset",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SmartTubService.SET_PRIMARY_FILTRATION,
        entity_domain=SENSOR_DOMAIN,
        schema=SET_PRIMARY_FILTRATION_SCHEMA,
        func="async_set_primary_filtration",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SmartTubService.SET_SECONDARY_FILTRATION,
        entity_domain=SENSOR_DOMAIN,
        schema=SET_SECONDARY_FILTRATION_SCHEMA,
        func="async_set_secondary_filtration",
    )
