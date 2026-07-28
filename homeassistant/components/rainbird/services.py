"""Rain Bird Irrigation system services."""

from functools import partial

import voluptuous as vol

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
from homeassistant.components.valve import DOMAIN as VALVE_DOMAIN, ValveEntity
from homeassistant.core import (
    HassJob,
    HassJobType,
    HomeAssistant,
    ServiceCall,
    callback,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import DATA_DOMAIN_PLATFORM_ENTITIES
from homeassistant.helpers.service import entity_service_call
from homeassistant.helpers.typing import VolDictType

from .const import ATTR_DURATION, DOMAIN

SERVICE_START_IRRIGATION = "start_irrigation"

SERVICE_SCHEMA_IRRIGATION: VolDictType = {
    vol.Required(ATTR_DURATION): cv.positive_float,
}


def _get_rainbird_irrigation_entities(hass: HomeAssistant) -> dict[str, Entity]:
    """Return all rainbird switch and valve entities eligible for irrigation."""
    data = hass.data.get(DATA_DOMAIN_PLATFORM_ENTITIES, {})
    entities: dict[str, Entity] = {}
    entities.update(data.get((SWITCH_DOMAIN, DOMAIN), {}))
    entities.update(data.get((VALVE_DOMAIN, DOMAIN), {}))
    return entities


async def _async_start_irrigation(entity: Entity, service_call: ServiceCall) -> None:
    """Start irrigation on a switch or valve entity."""
    if isinstance(entity, ValveEntity):
        await entity.async_open_valve(**service_call.data)
    elif isinstance(entity, SwitchEntity):
        await entity.async_turn_on(**service_call.data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_IRRIGATION,
        partial(
            entity_service_call,
            hass,
            partial(_get_rainbird_irrigation_entities, hass),
            HassJob(_async_start_irrigation),
        ),
        cv.make_entity_service_schema(SERVICE_SCHEMA_IRRIGATION),
        job_type=HassJobType.Coroutinefunction,
    )
