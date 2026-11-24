"""Services for Daikin Onecta."""

from datetime import date

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .climate import DaikinClimate
from .const import DOMAIN

SERVICE_SET_HOLIDAY_PERIOD = "set_holiday_period"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Daikin Onecta actions."""

    async def async_set_holiday_period(
        entities: list[DaikinClimate], service_call: ServiceCall
    ) -> None:
        """Set a custom holiday period for each targeted climate zone."""
        start_date: date = service_call.data["start_date"]
        end_date: date = service_call.data["end_date"]
        climate_entities: dict[tuple[str, str], DaikinClimate] = {}
        for entity in entities:
            climate_entities.setdefault(entity.management_point_identity, entity)

        # Validate every zone before issuing any cloud writes.
        for entity in climate_entities.values():
            entity.validate_holiday_period(start_date, end_date)
        for entity in climate_entities.values():
            await entity.async_set_holiday_period(start_date, end_date)

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HOLIDAY_PERIOD,
        entity_domain=CLIMATE_DOMAIN,
        func=async_set_holiday_period,
        schema={
            probatio.Required("start_date"): cv.date,
            probatio.Required("end_date"): cv.date,
        },
    )
