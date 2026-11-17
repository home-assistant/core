"""Services for the Snooz integration."""

from enum import StrEnum

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DEFAULT_TRANSITION_DURATION, DOMAIN


class SnoozService(StrEnum):
    """Store keys for Snooz services."""

    TRANSITION_ON = "transition_on"
    TRANSITION_OFF = "transition_off"


class SnoozServiceArgument(StrEnum):
    """Store keys for Snooz service arguments."""

    VOLUME = "volume"
    DURATION = "duration"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Snooz integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SnoozService.TRANSITION_ON,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Optional(SnoozServiceArgument.VOLUME): probatio.All(
                probatio.Coerce(int), probatio.Percentage()
            ),
            probatio.Optional(
                SnoozServiceArgument.DURATION, default=DEFAULT_TRANSITION_DURATION
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=300)),
        },
        func="async_transition_on",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SnoozService.TRANSITION_OFF,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Optional(
                SnoozServiceArgument.DURATION, default=DEFAULT_TRANSITION_DURATION
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=300))
        },
        func="async_transition_off",
    )
