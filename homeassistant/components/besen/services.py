"""Services for the Besen integration."""

from datetime import timedelta

from besen.const import MAX_CHARGE_DURATION_MINUTES
import probatio

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_DURATION = "duration"
ATTR_START = "start"

SERVICE_START_CHARGING = "start_charging"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Besen integration."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_CHARGING,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Optional(ATTR_START): cv.datetime,
            probatio.Optional(ATTR_DURATION): probatio.All(
                cv.time_period,
                probatio.Range(
                    min=timedelta(minutes=1),
                    max=timedelta(minutes=MAX_CHARGE_DURATION_MINUTES),
                ),
            ),
        },
        func="async_start_charging",
    )
