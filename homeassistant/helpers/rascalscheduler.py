"""Helpers to execute rascal entities."""
from __future__ import annotations

import logging
import re

from homeassistant.const import (
    CONF_ENTITY_ID,
    DOMAIN_AUTOMATION,
    DOMAIN_PERSON,
    DOMAIN_RASCALSCHEDULER,
    DOMAIN_SCRIPT,
    DOMAIN_TTS,
    DOMAIN_ZONE,
    NAME_SUN_NEXT_DAWN,
    NAME_SUN_NEXT_DUSK,
    NAME_SUN_NEXT_MIDNIGHT,
    NAME_SUN_NEXT_NOON,
    NAME_SUN_NEXT_RISING,
    NAME_SUN_NEXT_SETTING,
)
from homeassistant.core import HomeAssistant

from . import entity_registry as er

_LOGGER = logging.getLogger(__name__)

CONF_ENTITY_REGISTRY = "entity_registry"


def add_entity_in_lineage(hass: HomeAssistant, entity_id: str) -> None:
    """Create a queue for entity id in the lineage table."""
    domains = [DOMAIN_SCRIPT, DOMAIN_AUTOMATION, DOMAIN_PERSON, DOMAIN_ZONE, DOMAIN_TTS]
    full_names = [
        NAME_SUN_NEXT_SETTING,
        NAME_SUN_NEXT_RISING,
        NAME_SUN_NEXT_DAWN,
        NAME_SUN_NEXT_DUSK,
        NAME_SUN_NEXT_MIDNIGHT,
        NAME_SUN_NEXT_NOON,
    ]

    domain, full_name = entity_id.split(".")

    if full_name is not None:
        if domain not in domains and full_name not in full_names:
            _LOGGER.info("Create queue: %s", entity_id)
            rascal = hass.data.get(DOMAIN_RASCALSCHEDULER)
            if rascal is not None:
                rascal.lienage_table.add_entity(entity_id)


def delete_entity_in_lineage(hass: HomeAssistant, entity_id: str) -> None:
    """Delete x entity queue."""

    rascal = hass.data.get(DOMAIN_RASCALSCHEDULER)

    if rascal is not None:
        rascal.lineage_table.delete_entity(entity_id)
        _LOGGER.info("Delete queue: %s", entity_id)


def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises ValueError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.device_id is None:
        raise ValueError(f"Entity {entity_id} is not a valid entity.")

    return str(entity_entry.device_id)


def async_get_entity_id_from_number(hass: HomeAssistant, entity_id: str) -> str:
    """Get entity_id from number."""
    pattern = re.compile("^[^.]+[.][^.]+$")
    if not pattern.match(entity_id):
        registry = hass.data[CONF_ENTITY_REGISTRY]
        return str(registry.async_get(entity_id).as_partial_dict[CONF_ENTITY_ID])

    return str(entity_id)


def async_get_routine_id(action_id: str) -> str:
    """Get routine id from action id."""
    return action_id.split(".")[0]
