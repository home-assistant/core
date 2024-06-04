"""Define RainMachine utilities."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import LOGGER


class RunStates(StrEnum):
    """Define an enum for program/zone run states."""

    NOT_RUNNING = "Not Running"
    QUEUED = "Queued"
    RUNNING = "Running"


RUN_STATE_MAP = {
    0: RunStates.NOT_RUNNING,
    1: RunStates.RUNNING,
    2: RunStates.QUEUED,
}


@dataclass
class EntityDomainReplacementStrategy:
    """Define an entity replacement."""

    old_domain: str
    old_unique_id: str
    replacement_entity_id: str
    breaks_in_ha_version: str
    remove_old_entity: bool = True


@callback
def async_finish_entity_domain_replacements(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entity_replacement_strategies: Iterable[EntityDomainReplacementStrategy],
) -> None:
    """Remove old entities and create a repairs issue with info on their replacement."""
    ent_reg = er.async_get(hass)
    for strategy in entity_replacement_strategies:
        try:
            [registry_entry] = [
                registry_entry
                for registry_entry in ent_reg.entities.get_entries_for_config_entry_id(
                    entry.entry_id
                )
                if registry_entry.domain == strategy.old_domain
                and registry_entry.unique_id == strategy.old_unique_id
            ]
        except ValueError:
            continue

        old_entity_id = registry_entry.entity_id
        if strategy.remove_old_entity:
            LOGGER.info('Removing old entity: "%s"', old_entity_id)
            ent_reg.async_remove(old_entity_id)


def key_exists(data: dict[str, Any], search_key: str) -> bool:
    """Return whether a key exists in a nested dict."""
    for key, value in data.items():
        if key == search_key:
            return True
        if isinstance(value, dict):
            return key_exists(value, search_key)
    return False
