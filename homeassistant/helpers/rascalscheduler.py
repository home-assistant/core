"""Helpers to execute rascal entities."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import TYPE_CHECKING, Optional

import shortuuid

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

if TYPE_CHECKING:
    from homeassistant.components.rasc import RascalScheduler

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

    if full_name:
        if domain not in domains and full_name not in full_names:
            _LOGGER.info("Create queue: %s", entity_id)
            rascal: Optional[RascalScheduler] = hass.data.get(DOMAIN_RASCALSCHEDULER)
            if rascal:
                rascal.lineage_table.add_entity(entity_id)
                rascal.add_entity(entity_id)


def delete_entity_in_lineage(hass: HomeAssistant, entity_id: str) -> None:
    """Delete x entity queue."""

    rascal: Optional[RascalScheduler] = hass.data.get(DOMAIN_RASCALSCHEDULER)

    if rascal:
        rascal.lineage_table.delete_entity(entity_id)
        rascal.delete_entity(entity_id)
        _LOGGER.info("Delete queue: %s", entity_id)


def get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises ValueError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.device_id is None:
        raise ValueError(f"Entity {entity_id} is not a valid entity.")

    return str(entity_entry.device_id)


def get_entity_id_from_number(hass: HomeAssistant, entity_id: str) -> str:
    """Get entity_id from number."""
    pattern = re.compile("^[^.]+[.][^.]+$")
    if not pattern.match(entity_id):
        registry = hass.data[CONF_ENTITY_REGISTRY]
        return str(registry.async_get(entity_id).as_partial_dict[CONF_ENTITY_ID])

    return str(entity_id)


def get_routine_id(action_id: str) -> str:
    """Get routine id from action id."""
    return action_id.split(".")[0]


def generate_duration() -> timedelta:
    """Get a random duration."""
    return timedelta(seconds=2)


def string_to_datetime(dt: str) -> datetime:
    """Convert string into datetime."""
    return datetime.strptime(
        datetime.now().strftime("%Y-%m-%d") + " " + dt, "%Y-%m-%d %H%M%S"
    )


def datetime_to_string(dt: datetime) -> str:
    """Convert datetime to string."""
    return dt.strftime("%H%M%S")


def generate_short_uuid(size: int = 5) -> str:
    """Generate short uuid."""
    return shortuuid.ShortUUID().random(length=size)
