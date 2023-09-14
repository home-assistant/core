"""Diagnostics support for MQTT."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import device_tracker
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback, split_entity_id
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from . import debug_info, is_connected
from .util import get_mqtt_data

REDACT_CONFIG = {CONF_PASSWORD, CONF_USERNAME}
REDACT_STATE_DEVICE_TRACKER = {ATTR_LATITUDE, ATTR_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return _async_get_diagnostics(hass, entry)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    return _async_get_diagnostics(hass, entry, device)


@callback
def _async_get_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry | None = None,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    mqtt_instance = get_mqtt_data(hass).client
    if TYPE_CHECKING:
        assert mqtt_instance is not None

    redacted_config = async_redact_data(mqtt_instance.conf, REDACT_CONFIG)

    data = {
        "connected": is_connected(hass),
        "mqtt_config": redacted_config,
    }

    if device:
        data["device"] = _async_device_as_dict(hass, device)
        data["mqtt_debug_info"] = debug_info.info_for_device(hass, device.id)
    else:
        device_registry = dr.async_get(hass)
        data.update(
            devices=[
                _async_device_as_dict(hass, device)
                for device in dr.async_entries_for_config_entry(
                    device_registry, entry.entry_id
                )
            ],
            mqtt_debug_info=debug_info.info_for_config_entry(hass),
        )

    return data


@callback
def _async_device_as_dict(hass: HomeAssistant, device: DeviceEntry) -> dict[str, Any]:
    """Represent an MQTT device as a dictionary."""

    # Gather information how this MQTT device is represented in Home Assistant
    entity_registry = er.async_get(hass)
    data: dict[str, Any] = {
        "id": device.id,
        "name": device.name,
        "name_by_user": device.name_by_user,
        "disabled": device.disabled,
        "disabled_by": device.disabled_by,
        "entities": [],
    }

    entities = er.async_entries_for_device(
        entity_registry,
        device_id=device.id,
        include_disabled_entities=True,
    )

    for entity_entry in entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = dict(state.as_dict())

            # The context doesn't provide useful information in this case.
            state_dict.pop("context", None)

            entity_domain = split_entity_id(state.entity_id)[0]

            # Retract some sensitive state attributes
            if entity_domain == device_tracker.DOMAIN:
                state_dict["attributes"] = async_redact_data(
                    state_dict["attributes"], REDACT_STATE_DEVICE_TRACKER
                )

        data["entities"].append(
            {
                "device_class": entity_entry.device_class,
                "disabled_by": entity_entry.disabled_by,
                "disabled": entity_entry.disabled,
                "entity_category": entity_entry.entity_category,
                "entity_id": entity_entry.entity_id,
                "icon": entity_entry.icon,
                "original_device_class": entity_entry.original_device_class,
                "original_icon": entity_entry.original_icon,
                "state": state_dict,
                "unit_of_measurement": entity_entry.unit_of_measurement,
            }
        )

    return data
