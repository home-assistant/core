"""Services for the vacuum integration."""

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service as service_helper

from .const import (
    ATTR_FAN_SPEED,
    ATTR_PARAMS,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_CLEAN_AREA,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    VacuumEntityFeature,
)

if TYPE_CHECKING:
    from . import StateVacuumEntity

_LOGGER = logging.getLogger(__name__)


async def _async_clean_area(
    entities: list[StateVacuumEntity], call: ServiceCall
) -> None:
    """Perform an area clean.

    Calls async_clean_segments for each entity.
    """
    data = dict(call.data)
    cleaning_area_id: list[str] = data.pop("cleaning_area_id")

    entity_data: list[tuple[StateVacuumEntity, dict[str, Any]]] = []
    handled_areas: set[str] = set()
    for entity in entities:
        if entity.registry_entry is None:
            raise RuntimeError(
                "Cannot perform area clean, registry entry is not set for"
                f" {entity.entity_id}"
            )

        options: Mapping[str, Any] = entity.registry_entry.options.get(DOMAIN, {})
        area_mapping: dict[str, list[str]] | None = options.get("area_mapping")

        if area_mapping is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="area_mapping_not_configured",
                translation_placeholders={"entity_id": entity.entity_id},
            )

        # We use a dict to preserve the order of segments.
        segment_ids: dict[str, None] = {}
        for area_id in cleaning_area_id:
            if (segments := area_mapping.get(area_id)) is None:
                continue
            handled_areas.add(area_id)
            for segment_id in segments:
                segment_ids[segment_id] = None

        if not segment_ids:
            _LOGGER.debug(
                "No segments found for cleaning_area_id %s on vacuum %s",
                cleaning_area_id,
                entity.entity_id,
            )
            continue

        entity_data.append((entity, {"segment_ids": list(segment_ids), **data}))

    if entity_data:
        await service_helper.async_handle_entity_calls(
            "async_clean_segments", entity_data, context=call.context
        )

    unhandled_areas = set(cleaning_area_id) - handled_areas
    if unhandled_areas:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="areas_not_mapped",
            translation_placeholders={"areas": ", ".join(sorted(unhandled_areas))},
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the vacuum services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_START,
        None,
        "async_start",
        [VacuumEntityFeature.START],
    )
    component.async_register_entity_service(
        SERVICE_PAUSE,
        None,
        "async_pause",
        [VacuumEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_RETURN_TO_BASE,
        None,
        "async_return_to_base",
        [VacuumEntityFeature.RETURN_HOME],
    )
    component.async_register_entity_service(
        SERVICE_CLEAN_SPOT,
        None,
        "async_clean_spot",
        [VacuumEntityFeature.CLEAN_SPOT],
    )
    component.async_register_batched_entity_service(
        SERVICE_CLEAN_AREA,
        {
            probatio.Required("cleaning_area_id"): probatio.All(cv.ensure_list, [str]),
        },
        _async_clean_area,
        [VacuumEntityFeature.CLEAN_AREA],
    )
    component.async_register_entity_service(
        SERVICE_LOCATE,
        None,
        "async_locate",
        [VacuumEntityFeature.LOCATE],
    )
    component.async_register_entity_service(
        SERVICE_STOP,
        None,
        "async_stop",
        [VacuumEntityFeature.STOP],
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_SPEED,
        {probatio.Required(ATTR_FAN_SPEED): cv.string},
        "async_set_fan_speed",
        [VacuumEntityFeature.FAN_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            probatio.Required(ATTR_COMMAND): cv.string,
            probatio.Optional(ATTR_PARAMS): probatio.Any(dict, cv.ensure_list),
        },
        "async_send_command",
        [VacuumEntityFeature.SEND_COMMAND],
    )
