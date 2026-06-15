"""PowerShades services."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .coordinator import PowerShadesConfigEntry, PowerShadesCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_id})


def _get_coordinator(hass: HomeAssistant, call: ServiceCall) -> PowerShadesCoordinator:
    """Resolve the coordinator for the entity targeted by a service call."""
    entity_id = call.data[ATTR_ENTITY_ID]
    entity = er.async_get(hass).async_get(entity_id)
    if entity is None or entity.platform != DOMAIN or entity.config_entry_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )
    entry: PowerShadesConfigEntry | None = hass.config_entries.async_get_entry(
        entity.config_entry_id
    )
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"entity_id": entity_id},
        )
    return entry.runtime_data


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up PowerShades services."""

    async def toggle_shade(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_toggle()

    async def set_upper_limit(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_set_upper_limit()

    async def set_lower_limit(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_set_lower_limit()

    async def clear_limits(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_clear_limits()

    async def step_up(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_step_up()

    async def step_down(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_step_down()

    async def jog_up(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_jog_up()

    async def jog_down(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_jog_down()

    async def set_shade_name(call: ServiceCall) -> None:
        name = call.data["name"].strip()
        if not name or len(name) > 50 or not name.isascii():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_shade_name",
            )
        await _get_coordinator(hass, call).async_set_shade_name(name)

    for name, handler in (
        ("toggle_shade", toggle_shade),
        ("set_upper_limit", set_upper_limit),
        ("set_lower_limit", set_lower_limit),
        ("clear_limits", clear_limits),
        ("step_up", step_up),
        ("step_down", step_down),
        ("jog_up", jog_up),
        ("jog_down", jog_down),
    ):
        hass.services.async_register(DOMAIN, name, handler, schema=SERVICE_SCHEMA)

    hass.services.async_register(
        DOMAIN,
        "set_shade_name",
        set_shade_name,
        schema=SERVICE_SCHEMA.extend({vol.Required("name"): cv.string}),
    )
