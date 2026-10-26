"""Services for the schedule integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

from homeassistant.const import CONF_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers.service import async_register_admin_service

from .const import DATA_SCHEDULE, DOMAIN

if TYPE_CHECKING:
    from .entity import Schedule


class ScheduleService(StrEnum):
    """Store keys for schedule services."""

    GET = "get_schedule"
    RELOAD = "reload"


async def _async_get_schedule_service(
    schedule: Schedule, service_call: ServiceCall
) -> ServiceResponse:
    """Return the schedule configuration."""
    return schedule.get_schedule()


async def _async_reload_service(service_call: ServiceCall) -> None:
    """Reload yaml entities."""
    hass = service_call.hass
    data = hass.data[DATA_SCHEDULE]
    conf = await data.component.async_prepare_reload(skip_reset=True)
    await data.yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in conf.get(DOMAIN, {}).items()]
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the schedule services."""
    async_register_admin_service(
        hass,
        DOMAIN,
        ScheduleService.RELOAD,
        _async_reload_service,
    )

    hass.data[DATA_SCHEDULE].component.async_register_entity_service(
        ScheduleService.GET,
        {},
        _async_get_schedule_service,
        supports_response=SupportsResponse.ONLY,
    )
