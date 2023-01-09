"""Diagnostics support for HomeKit."""
from __future__ import annotations

from typing import Any

from pyhap.accessory_driver import AccessoryDriver
from pyhap.state import State

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import HomeKit
from .accessories import HomeAccessory, HomeBridge
from .const import DOMAIN, HOMEKIT

TO_REDACT = {"access_token", "entity_picture"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    homekit: HomeKit = hass.data[DOMAIN][entry.entry_id][HOMEKIT]
    data: dict[str, Any] = {
        "status": homekit.status,
        "config-entry": {
            "title": entry.title,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
    }
    if homekit.iid_storage:
        data["iid_storage"] = homekit.iid_storage.allocations
    if not homekit.driver:  # not started yet or startup failed
        return data
    driver: AccessoryDriver = homekit.driver
    if driver.accessory:
        if isinstance(driver.accessory, HomeBridge):
            data["bridge"] = _get_bridge_diagnostics(hass, driver.accessory)
        else:
            data["accessory"] = _get_accessory_diagnostics(hass, driver.accessory)
    data.update(driver.get_accessories())
    state: State = driver.state
    data.update(
        {
            "client_properties": {
                str(client): props for client, props in state.client_properties.items()
            },
            "config_version": state.config_version,
            "pairing_id": state.mac,
        }
    )
    return data


def _get_bridge_diagnostics(hass: HomeAssistant, bridge: HomeBridge) -> dict[int, Any]:
    """Return diagnostics for a bridge."""
    return {
        aid: _get_accessory_diagnostics(hass, accessory)
        for aid, accessory in bridge.accessories.items()
    }


def _get_accessory_diagnostics(
    hass: HomeAssistant, accessory: HomeAccessory
) -> dict[str, Any]:
    """Return diagnostics for an accessory."""
    entity_state = None
    if accessory.entity_id:
        entity_state = hass.states.get(accessory.entity_id)
    data = {
        "aid": accessory.aid,
        "config": accessory.config,
        "category": accessory.category,
        "name": accessory.display_name,
        "entity_id": accessory.entity_id,
    }
    if entity_state:
        data["entity_state"] = async_redact_data(entity_state, TO_REDACT)
    return data
