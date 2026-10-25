"""Services for the SmartTub integration."""

import probatio
import smarttub

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import ATTR_DURATION, ATTR_REMINDER_DAYS, ATTR_START_HOUR, DOMAIN

RESET_REMINDER_SCHEMA: VolDictType = {
    probatio.Required(ATTR_REMINDER_DAYS): probatio.All(
        probatio.Coerce(int), probatio.Range(min=30, max=365)
    )
}
SNOOZE_REMINDER_SCHEMA: VolDictType = {
    probatio.Required(ATTR_REMINDER_DAYS): probatio.All(
        probatio.Coerce(int), probatio.Range(min=10, max=120)
    )
}
SET_PRIMARY_FILTRATION_SCHEMA = probatio.All(
    probatio.AtLeastOne(ATTR_DURATION, ATTR_START_HOUR),
    cv.make_entity_service_schema(
        {
            probatio.Optional(ATTR_DURATION): probatio.All(
                int, probatio.Range(min=1, max=24)
            ),
            probatio.Optional(ATTR_START_HOUR): probatio.All(
                int, probatio.Range(min=0, max=23)
            ),
        },
    ),
)
SET_SECONDARY_FILTRATION_SCHEMA: VolDictType = {
    probatio.Required(ATTR_MODE): probatio.In(
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
        "snooze_reminder",
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=SNOOZE_REMINDER_SCHEMA,
        func="async_snooze",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "reset_reminder",
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema=RESET_REMINDER_SCHEMA,
        func="async_reset",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_primary_filtration",
        entity_domain=SENSOR_DOMAIN,
        schema=SET_PRIMARY_FILTRATION_SCHEMA,
        func="async_set_primary_filtration",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_secondary_filtration",
        entity_domain=SENSOR_DOMAIN,
        schema=SET_SECONDARY_FILTRATION_SCHEMA,
        func="async_set_secondary_filtration",
    )
