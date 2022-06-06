"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_LOGBOOK_ENTRY,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HomeAssistant,
    State,
    callback,
    is_callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    ALL_EVENT_TYPES_EXCEPT_STATE_CHANGED,
    DOMAIN,
    ENTITY_EVENTS_WITHOUT_CONFIG_ENTRY,
)
from .models import LazyEventPartialState


def async_filter_entities(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Filter out any entities that logbook will not produce results for."""
    ent_reg = er.async_get(hass)
    return [
        entity_id
        for entity_id in entity_ids
        if not _is_entity_id_filtered(hass, ent_reg, entity_id)
    ]


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


@callback
def async_subscribe_events(
    hass: HomeAssistant,
    subscriptions: list[CALLBACK_TYPE],
    target: Callable[[Event], None],
    event_types: tuple[str, ...],
    entity_ids: list[str] | None,
    device_ids: list[str] | None,
) -> None:
    """Subscribe to events for the entities and devices or all.

    These are the events we need to listen for to do
    the live logbook stream.
    """
    ent_reg = er.async_get(hass)
    assert is_callback(target), "target must be a callback"
    event_forwarder = target

    if entity_ids or device_ids:
        entity_ids_set = set(entity_ids) if entity_ids else set()
        device_ids_set = set(device_ids) if device_ids else set()

        @callback
        def _forward_events_filtered(event: Event) -> None:
            event_data = event.data
            if (
                entity_ids_set and event_data.get(ATTR_ENTITY_ID) in entity_ids_set
            ) or (device_ids_set and event_data.get(ATTR_DEVICE_ID) in device_ids_set):
                target(event)

        event_forwarder = _forward_events_filtered

    for event_type in event_types:
        subscriptions.append(
            hass.bus.async_listen(event_type, event_forwarder, run_immediately=True)
        )

    @callback
    def _forward_state_events_filtered(event: Event) -> None:
        if event.data.get("old_state") is None or event.data.get("new_state") is None:
            return
        state: State = event.data["new_state"]
        if not _is_state_filtered(ent_reg, state):
            target(event)

    if device_ids and not entity_ids:
        # No entities to subscribe to but we are filtering
        # on device ids so we do not want to get any state
        # changed events
        return

    if entity_ids:
        subscriptions.append(
            async_track_state_change_event(
                hass, entity_ids, _forward_state_events_filtered
            )
        )
        return

    # We want the firehose
    subscriptions.append(
        hass.bus.async_listen(
            EVENT_STATE_CHANGED,
            _forward_state_events_filtered,
            run_immediately=True,
        )
    )


def is_sensor_continuous(ent_reg: er.EntityRegistry, entity_id: str) -> bool:
    """Determine if a sensor is continuous by checking its state class.

    Sensors with a unit_of_measurement are also considered continuous, but are filtered
    already by the SQL query generated by _get_events
    """
    if not (entry := ent_reg.async_get(entity_id)):
        # Entity not registered, so can't have a state class
        return False
    return (
        entry.capabilities is not None
        and entry.capabilities.get(ATTR_STATE_CLASS) is not None
    )


def _is_state_filtered(ent_reg: er.EntityRegistry, state: State) -> bool:
    """Check if the logbook should filter a state.

    Used when we are in live mode to ensure
    we only get significant changes (state.last_changed != state.last_updated)
    """
    return bool(
        state.last_changed != state.last_updated
        or ATTR_UNIT_OF_MEASUREMENT in state.attributes
        or is_sensor_continuous(ent_reg, state.entity_id)
    )


def _is_entity_id_filtered(
    hass: HomeAssistant, ent_reg: er.EntityRegistry, entity_id: str
) -> bool:
    """Check if the logbook should filter an entity.

    Used to setup listeners and which entities to select
    from the database when a list of entities is requested.
    """
    return bool(
        (state := hass.states.get(entity_id))
        and (ATTR_UNIT_OF_MEASUREMENT in state.attributes)
        or is_sensor_continuous(ent_reg, entity_id)
    )
