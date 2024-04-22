"""Diagnostics support for MelCloud."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    ent_reg = er.async_get(hass)
    entities = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    ]

    entity_states = {entity: hass.states.get(entity) for entity in entities}

    data = hass.data[DOMAIN][entry.entry_id]

    ata_devices: list = {}
    atw_devices: list = {}

    if data["ata"]:
        ata_devices_list = hass.data[DOMAIN][entry.entry_id]["ata"]
        ata_devices = {device: device for device in ata_devices_list}

    if data["atw"]:
        atw_devices_list = hass.data[DOMAIN][entry.entry_id]["atw"]
        atw_devices = {device: device for device in atw_devices_list}

    return {
        "entry": entry.as_dict(),
        "entities": entity_states,
        "ata_devices": ata_devices,
        "atw_devices": atw_devices,
    }
