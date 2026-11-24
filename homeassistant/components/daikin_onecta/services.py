"""Services for Daikin Onecta."""

from datetime import date
from enum import StrEnum
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


class OnectaService(StrEnum):
    """Store keys for Daikin Onecta services."""

    GET_SCHEDULE_DATA = "get_schedule_data"
    SET_HOLIDAY_PERIOD = "set_holiday_period"
    SET_SCHEDULE_DATA = "set_schedule_data"


class OnectaServiceArgument(StrEnum):
    """Store keys for Daikin Onecta service arguments."""

    END_DATE = "end_date"
    SCHEDULES = "schedules"
    START_DATE = "start_date"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Daikin Onecta actions."""

    async def async_set_holiday_period(
        entities: list[DaikinClimate], service_call: ServiceCall
    ) -> None:
        """Set a custom holiday period for each targeted climate zone."""
        start_date: date = service_call.data[OnectaServiceArgument.START_DATE]
        end_date: date = service_call.data[OnectaServiceArgument.END_DATE]
        climate_entities = _climate_entities_by_management_point(entities)

        # Validate every zone before issuing any cloud writes.
        for entity in climate_entities.values():
            entity.validate_holiday_period(start_date, end_date)
        for entity in climate_entities.values():
            await entity.async_set_holiday_period(start_date, end_date)

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        OnectaService.SET_HOLIDAY_PERIOD,
        entity_domain=CLIMATE_DOMAIN,
        func=async_set_holiday_period,
        schema={
            probatio.Required(OnectaServiceArgument.START_DATE): cv.date,
            probatio.Required(OnectaServiceArgument.END_DATE): cv.date,
        },
    )

    async def async_get_schedule_data(
        entities: list[DaikinClimate], _service_call: ServiceCall
    ) -> EntityServiceResponse:
        """Return editable raw schedule definitions for each selected zone."""
        climate_entities = _climate_entities_by_management_point(entities)
        return {
            entity.entity_id: cast(
                JsonObjectType,
                {OnectaServiceArgument.SCHEDULES: entity.get_schedule_data()},
            )
            for entity in climate_entities.values()
            if entity.entity_id is not None
        }

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        OnectaService.GET_SCHEDULE_DATA,
        entity_domain=CLIMATE_DOMAIN,
        func=async_get_schedule_data,
        schema={},
        supports_response=SupportsResponse.ONLY,
    )

    async def async_set_schedule_data(
        entities: list[DaikinClimate], service_call: ServiceCall
    ) -> None:
        """Replace the schedules on each selected zone with supplied raw data."""
        schedule_data: dict[str, Any] = service_call.data[
            OnectaServiceArgument.SCHEDULES
        ]
        climate_entities = _climate_entities_by_management_point(entities)
        for entity in climate_entities.values():
            entity.validate_schedule_data(schedule_data)
        for entity in climate_entities.values():
            await entity.async_set_schedule_data(schedule_data)

    service.async_register_batched_platform_entity_service(
        hass,
        DOMAIN,
        OnectaService.SET_SCHEDULE_DATA,
        entity_domain=CLIMATE_DOMAIN,
        func=async_set_schedule_data,
        schema={probatio.Required(OnectaServiceArgument.SCHEDULES): dict},
    )


def _climate_entities_by_management_point(
    entities: list[DaikinClimate],
) -> dict[tuple[str, str], DaikinClimate]:
    """Select one climate entity per Daikin management point."""
    climate_entities: dict[tuple[str, str], DaikinClimate] = {}
    for entity in entities:
        climate_entities.setdefault(entity.management_point_identity, entity)
    return climate_entities
