"""Services for the Workday integration."""

from enum import StrEnum

import probatio

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class WorkdayService(StrEnum):
    """Store keys for Workday services."""

    CHECK_DATE = "check_date"


class WorkdayServiceArgument(StrEnum):
    """Store keys for Workday service arguments."""

    CHECK_DATE = "check_date"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Workday integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        WorkdayService.CHECK_DATE,
        entity_domain=BINARY_SENSOR_DOMAIN,
        schema={probatio.Required(WorkdayServiceArgument.CHECK_DATE): cv.date},
        func="check_date",
        supports_response=SupportsResponse.ONLY,
    )
