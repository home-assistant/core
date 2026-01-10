"""Services for the SwitchBot integration."""

from __future__ import annotations

import asyncio
from typing import cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SENSOR_TYPE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.target import TargetSelection
from homeassistant.util.json import JsonValueType

from .const import DOMAIN, SupportedModels
from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator

SERVICE_ADD_PASSWORD = "add_password"
SERVICE_GET_PASSWORD_COUNT = "get_password_count"

ATTR_PASSWORD = "password"

_PASSWORD_VALIDATOR = vol.All(cv.string, cv.matches_regex(r"^\d{6,12}$"))

SCHEMA_ADD_PASSWORD_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_PASSWORD): _PASSWORD_VALIDATOR,
        **cv.TARGET_SERVICE_FIELDS,
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_GET_PASSWORD_COUNT_SERVICE = vol.Schema(
    {
        **cv.TARGET_SERVICE_FIELDS,
    },
    extra=vol.ALLOW_EXTRA,
)


@callback
def _async_get_switchbot_entry_for_entity_id(
    hass: HomeAssistant, entity_id: str
) -> SwitchbotConfigEntry:
    """Return the loaded SwitchBot config entry for an entity id."""
    entity_registry = er.async_get(hass)
    if not (entity_entry := entity_registry.async_get(entity_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity_id",
            translation_placeholders={"entity_id": entity_id},
        )

    if entity_entry.config_entry_id is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_without_config_entry",
            translation_placeholders={"entity_id": entity_id},
        )

    entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_belonging",
            translation_placeholders={"entity_id": entity_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"entity_id": entity_id},
        )

    return cast(SwitchbotConfigEntry, entry)


def _is_supported_keypad(entry: SwitchbotConfigEntry) -> bool:
    """Return if the entry is a supported keypad model."""
    allowed_sensor_types = {
        SupportedModels.KEYPAD_VISION.value,
        SupportedModels.KEYPAD_VISION_PRO.value,
    }
    return entry.data.get(CONF_SENSOR_TYPE) in allowed_sensor_types


@callback
def _async_extract_target_entity_ids(call: ServiceCall) -> set[str]:
    """Extract entity ids from a service call target."""
    selection = TargetSelection(call.data)

    return set(selection.entity_ids)


@callback
def _async_targets(
    hass: HomeAssistant, entity_ids: set[str]
) -> tuple[dict[str, SwitchbotDataUpdateCoordinator], dict[str, set[str]]]:
    """Group targets by config entry id."""
    coordinators_by_entry_id: dict[str, SwitchbotDataUpdateCoordinator] = {}
    entity_ids_by_entry_id: dict[str, set[str]] = {}

    for entity_id in entity_ids:
        entry = _async_get_switchbot_entry_for_entity_id(hass, entity_id)
        if not _is_supported_keypad(entry):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_keypad_vision_device",
                translation_placeholders={"entity_id": entity_id},
            )

        coordinators_by_entry_id.setdefault(entry.entry_id, entry.runtime_data)
        entity_ids_by_entry_id.setdefault(entry.entry_id, set()).add(entity_id)

    return coordinators_by_entry_id, entity_ids_by_entry_id


async def async_add_password(call: ServiceCall) -> None:
    """Add a password to a SwitchBot keypad device."""
    password: str = call.data[ATTR_PASSWORD]
    entity_ids = _async_extract_target_entity_ids(call)

    coordinators_by_entry_id, _ = _async_targets(call.hass, entity_ids)

    await asyncio.gather(
        *(
            coordinator.device.add_password(password)
            for coordinator in coordinators_by_entry_id.values()
        )
    )


async def async_get_password_count(call: ServiceCall) -> ServiceResponse:
    """Return the password counts by credential type for the keypad device."""
    entity_ids = _async_extract_target_entity_ids(call)

    coordinators_by_entry_id, entity_ids_by_entry_id = _async_targets(
        call.hass, entity_ids
    )

    entry_ids = list(coordinators_by_entry_id)
    results = await asyncio.gather(
        *(
            coordinators_by_entry_id[entry_id].device.get_password_count()
            for entry_id in entry_ids
        )
    )

    result_by_entity_id: dict[str, dict[str, JsonValueType]] = {}
    for entry_id, result in zip(entry_ids, results, strict=True):
        for entity_id in entity_ids_by_entry_id[entry_id]:
            result_by_entity_id[entity_id] = result

    if len(entity_ids) == 1:
        return next(iter(result_by_entity_id.values()))

    entities: dict[str, JsonValueType] = dict(result_by_entity_id.items())
    return {"entities": entities}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the SwitchBot integration."""
    if not hass.services.has_service(DOMAIN, SERVICE_ADD_PASSWORD):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            async_add_password,
            schema=SCHEMA_ADD_PASSWORD_SERVICE,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_GET_PASSWORD_COUNT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_PASSWORD_COUNT,
            async_get_password_count,
            schema=SCHEMA_GET_PASSWORD_COUNT_SERVICE,
            supports_response=SupportsResponse.ONLY,
        )
