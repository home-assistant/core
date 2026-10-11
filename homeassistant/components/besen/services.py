"""Services for the Besen integration."""

from datetime import timedelta
from enum import StrEnum

from besen.const import MAX_CHARGE_DURATION_MINUTES
import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class BesenService(StrEnum):
    """Store keys for Besen services."""

    START_CHARGING = "start_charging"


class BesenServiceArgument(StrEnum):
    """Store keys for Besen service arguments."""

    DURATION = "duration"
    START = "start"


def _whole_minutes(value: timedelta) -> timedelta:
    """Validate a duration for the charger, which counts in whole minutes."""
    if value.total_seconds() % 60:
        raise probatio.Invalid("The duration must be a whole number of minutes")
    return value


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Besen integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BesenService.START_CHARGING,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Optional(BesenServiceArgument.START): cv.datetime,
            probatio.Optional(BesenServiceArgument.DURATION): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(minutes=1),
                    max=timedelta(minutes=MAX_CHARGE_DURATION_MINUTES),
                ),
                _whole_minutes,
            ),
        },
        func="async_start_charging",
    )
