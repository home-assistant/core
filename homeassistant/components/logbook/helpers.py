"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.const import EVENT_LOGBOOK_ENTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED,
    DOMAIN,
    ENTITY_EVENTS_WITHOUT_CONFIG_ENTRY,
)
from .models import LazyEventPartialState


def async_determine_event_types(
    hass: HomeAssistant, entity_ids: list[str] | None, device_ids: list[str] | None
) -> tuple[str, ...]:
    """Reduce the event types based on the entity ids and device ids."""
    external_events: dict[
        str, tuple[str, Callable[[LazyEventPartialState], dict[str, Any]]]
    ] = hass.data.get(DOMAIN, {})
    if not entity_ids and not device_ids:
        return (*ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED, *external_events)
    config_entry_ids: set[str] = set()
    intrested_event_types: set[str] = set()

    if entity_ids:
        #
        # Home Assistant doesn't allow firing events from
        # entities so we have a limited list to check
        #
        # automations and scripts can refer to entities
        # but they do not have a config entry so we need
        # to add them.
        #
        # We also allow entity_ids to be recorded via
        # manual logbook entries.
        #
        intrested_event_types |= ENTITY_EVENTS_WITHOUT_CONFIG_ENTRY

    if device_ids:
        dev_reg = dr.async_get(hass)
        for device_id in device_ids:
            if (device := dev_reg.async_get(device_id)) and device.config_entries:
                config_entry_ids |= device.config_entries
        interested_domains: set[str] = set()
        for entry_id in config_entry_ids:
            if entry := hass.config_entries.async_get_entry(entry_id):
                interested_domains.add(entry.domain)
        for external_event, domain_call in external_events.items():
            if domain_call[0] in interested_domains:
                intrested_event_types.add(external_event)

    return tuple(
        event_type
        for event_type in (EVENT_LOGBOOK_ENTRY, *external_events)
        if event_type in intrested_event_types
    )
