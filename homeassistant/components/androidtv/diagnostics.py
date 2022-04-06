"""Diagnostics support for AndroidTV."""
from __future__ import annotations

from typing import Any

import attr

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS, ATTR_IDENTIFIERS, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import ANDROID_DEV, DOMAIN, PROP_ETHMAC, PROP_SERIALNO, PROP_WIFIMAC

TO_REDACT = {CONF_UNIQUE_ID}  # UniqueID contain MAC Address
TO_REDACT_DEV = {PROP_ETHMAC, PROP_SERIALNO, PROP_WIFIMAC}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, dict[str, Any]]:
    """Return diagnostics for a config entry."""
    data = {"entry": async_redact_data(entry.as_dict(), TO_REDACT)}
    hass_data = hass.data[DOMAIN][entry.entry_id]

    # Get information from AndroidTV library
    aftv = hass_data[ANDROID_DEV]
    data_dev = {"device_class": aftv.DEVICE_CLASS}
    for prop, value in aftv.device_properties.items():
        if prop in TO_REDACT_DEV and value:
            data_dev[prop] = REDACTED
        else:
            data_dev[prop] = value
    data["device_properties"] = data_dev

    # Gather information how this AndroidTV device is represented in Home Assistant
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    hass_device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(entry.unique_id))}
    )
    if not hass_device:
        return data

    data["device"] = {
        **attr.asdict(hass_device),
        "entities": {},
    }
    data["device"][ATTR_IDENTIFIERS] = REDACTED
    if ATTR_CONNECTIONS in data["device"]:
        data["device"][ATTR_CONNECTIONS] = REDACTED

    hass_entities = er.async_entries_for_device(
        entity_registry,
        device_id=hass_device.id,
        include_disabled_entities=True,
    )

    for entity_entry in hass_entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = dict(state.as_dict())
            # The entity_id is already provided at root level.
            state_dict.pop("entity_id", None)
            # The context doesn't provide useful information in this case.
            state_dict.pop("context", None)

        entity_dict = async_redact_data(
            {
                **attr.asdict(
                    entity_entry, filter=lambda attr, value: attr.name != "entity_id"
                ),
                "state": state_dict,
            },
            TO_REDACT,
        )
        data["device"]["entities"][entity_entry.entity_id] = entity_dict

    return data
