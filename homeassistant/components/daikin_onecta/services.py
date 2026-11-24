"""Services for Daikin Onecta."""

from datetime import date
from typing import Any, cast

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.core import (
    EntityServiceResponse,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import config_validation as cv, service
from homeassistant.util.json import JsonObjectType

from .climate import DaikinClimate
from .const import DOMAIN

SERVICE_SET_HOLIDAY_PERIOD = "set_holiday_period"
SERVICE_GET_SCHEDULE_DATA = "get_schedule_data"
SERVICE_SET_SCHEDULE_DATA = "set_schedule_data"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Daikin Onecta actions."""

    async def async_set_holiday_period(
        entities: list[DaikinClimate], service_call: ServiceCall
    ) -> None:
        """Set a custom holiday period for each targeted climate zone."""
        start_date: date = service_call.data["start_date"]
        end_date: date = service_call.data["end_date"]
        climate_entities = _climate_entities_by_management_point(entities)

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

    async def async_get_schedule_data(
        entities: list[DaikinClimate], _service_call: ServiceCall
    ) -> EntityServiceResponse:
        """Return editable raw schedule definitions for each selected zone."""
        climate_entities = _climate_entities_by_management_point(entities)
        return {
            entity.entity_id: cast(
                JsonObjectType, {"schedules": entity.get_schedule_data()}
            )
            for entity in climate_entities.values()
            if entity.entity_id is not None
        }

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_SCHEDULE_DATA,
        entity_domain=CLIMATE_DOMAIN,
        func=async_get_schedule_data,
        schema={},
        supports_response=SupportsResponse.ONLY,
    )

    async def async_set_schedule_data(
        entities: list[DaikinClimate], service_call: ServiceCall
    ) -> None:
        """Replace the schedules on each selected zone with supplied raw data."""
        schedule_data: dict[str, Any] = service_call.data["schedules"]
        climate_entities = _climate_entities_by_management_point(entities)
        for entity in climate_entities.values():
            entity.validate_schedule_data(schedule_data)
        for entity in climate_entities.values():
            await entity.async_set_schedule_data(schedule_data)

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SCHEDULE_DATA,
        entity_domain=CLIMATE_DOMAIN,
        func=async_set_schedule_data,
        schema={probatio.Required("schedules"): dict},
    )


def _climate_entities_by_management_point(
    entities: list[DaikinClimate],
) -> dict[tuple[str, str], DaikinClimate]:
    """Select one climate entity per Daikin management point."""
    climate_entities: dict[tuple[str, str], DaikinClimate] = {}
    for entity in entities:
        climate_entities.setdefault(entity.management_point_identity, entity)
    return climate_entities
