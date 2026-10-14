"""Services for the Snooz integration."""

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import (
    ATTR_DURATION,
    ATTR_VOLUME,
    DEFAULT_TRANSITION_DURATION,
    DOMAIN,
    SERVICE_TRANSITION_OFF,
    SERVICE_TRANSITION_ON,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Snooz integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRANSITION_ON,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Optional(ATTR_VOLUME): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            ),
            probatio.Optional(
                ATTR_DURATION, default=DEFAULT_TRANSITION_DURATION
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=300)),
        },
        func="async_transition_on",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRANSITION_OFF,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Optional(
                ATTR_DURATION, default=DEFAULT_TRANSITION_DURATION
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=300))
        },
        func="async_transition_off",
    )
