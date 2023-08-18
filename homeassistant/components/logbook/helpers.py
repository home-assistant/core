"""Event parser and human readable log generator."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_DOMAIN,
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
    split_entity_id,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.typing import EventType

from .const import ALWAYS_CONTINUOUS_DOMAINS, AUTOMATION_EVENTS, BUILT_IN_EVENTS, DOMAIN
from .models import LogbookConfig


def async_filter_entities(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Filter out any entities that logbook will not produce results for."""
    ent_reg = er.async_get(hass)
    return [
        entity_id
        for entity_id in entity_ids
        if not _is_entity_id_filtered(hass, ent_reg, entity_id)
    ]


@callback
def _async_config_entries_for_ids(
    hass: HomeAssistant, entity_ids: list[str] | None, device_ids: list[str] | None
) -> set[str]:
    """Find the config entry ids for a set of entities or devices."""
    config_entry_ids: set[str] = set()
    if entity_ids:
        eng_reg = er.async_get(hass)
        for entity_id in entity_ids:
            if (entry := eng_reg.async_get(entity_id)) and entry.config_entry_id:
                config_entry_ids.add(entry.config_entry_id)
    if device_ids:
        dev_reg = dr.async_get(hass)
        for device_id in device_ids:
            if (device := dev_reg.async_get(device_id)) and device.config_entries:
                config_entry_ids |= device.config_entries
    return config_entry_ids


def async_determine_event_types(
    hass: HomeAssistant, entity_ids: list[str] | None, device_ids: list[str] | None
) -> tuple[str, ...]:
    """Reduce the event types based on the entity ids and device ids."""
    logbook_config: LogbookConfig = hass.data[DOMAIN]
    external_events = logbook_config.external_events
    if not entity_ids and not device_ids:
        return (*BUILT_IN_EVENTS, *external_events)

    interested_domains: set[str] = set()
    for entry_id in _async_config_entries_for_ids(hass, entity_ids, device_ids):
        if entry := hass.config_entries.async_get_entry(entry_id):
            interested_domains.add(entry.domain)

    #
    # automations and scripts can refer to entities or devices
    # but they do not have a config entry so we need
    # to add them since we have historically included
    # them when matching only on entities
    #
    intrested_event_types: set[str] = {
        external_event
        for external_event, domain_call in external_events.items()
        if domain_call[0] in interested_domains
    } | AUTOMATION_EVENTS
    if entity_ids:
        # We also allow entity_ids to be recorded via manual logbook entries.
        intrested_event_types.add(EVENT_LOGBOOK_ENTRY)

    return tuple(intrested_event_types)


@callback
def extract_attr(source: dict[str, Any], attr: str) -> list[str]:
    """Extract an attribute as a list or string."""
    if (value := source.get(attr)) is None:
        return []
    if isinstance(value, list):
        return value
    return str(value).split(",")


@callback
def event_forwarder_filtered(
    target: Callable[[Event], None],
    entities_filter: Callable[[str], bool] | None,
    entity_ids: list[str] | None,
    device_ids: list[str] | None,
) -> Callable[[Event], None]:
    """Make a callable to filter events."""
    if not entities_filter and not entity_ids and not device_ids:
        # No filter
        # - Script Trace (context ids)
        # - Automation Trace (context ids)
        return target

    if entities_filter:
        # We have an entity filter:
        # - Logbook panel

        @callback
        def _forward_events_filtered_by_entities_filter(event: Event) -> None:
            assert entities_filter is not None
            event_data = event.data
            entity_ids = extract_attr(event_data, ATTR_ENTITY_ID)
            if entity_ids and not any(
                entities_filter(entity_id) for entity_id in entity_ids
            ):
                return
            domain = event_data.get(ATTR_DOMAIN)
            if domain and not entities_filter(f"{domain}._"):
                return
            target(event)

        return _forward_events_filtered_by_entities_filter

    # We are filtering on entity_ids and/or device_ids:
    # - Areas
    # - Devices
    # - Logbook Card
    entity_ids_set = set(entity_ids) if entity_ids else set()
    device_ids_set = set(device_ids) if device_ids else set()

    @callback
    def _forward_events_filtered_by_device_entity_ids(event: Event) -> None:
        event_data = event.data
        if entity_ids_set.intersection(
            extract_attr(event_data, ATTR_ENTITY_ID)
        ) or device_ids_set.intersection(extract_attr(event_data, ATTR_DEVICE_ID)):
            target(event)

    return _forward_events_filtered_by_device_entity_ids


@callback
def async_subscribe_events(
    hass: HomeAssistant,
    subscriptions: list[CALLBACK_TYPE],
    target: Callable[[Event], None],
    event_types: tuple[str, ...],
    entities_filter: Callable[[str], bool] | None,
    entity_ids: list[str] | None,
    device_ids: list[str] | None,
) -> None:
    """Subscribe to events for the entities and devices or all.

    These are the events we need to listen for to do
    the live logbook stream.
    """
    ent_reg = er.async_get(hass)
    assert is_callback(target), "target must be a callback"
    event_forwarder = event_forwarder_filtered(
        target, entities_filter, entity_ids, device_ids
    )
    for event_type in event_types:
        subscriptions.append(
            hass.bus.async_listen(event_type, event_forwarder, run_immediately=True)
        )

    if device_ids and not entity_ids:
        # No entities to subscribe to but we are filtering
        # on device ids so we do not want to get any state
        # changed events
        return

    @callback
    def _forward_state_events_filtered(event: EventType[EventStateChangedData]) -> None:
        if (old_state := event.data["old_state"]) is None or (
            new_state := event.data["new_state"]
        ) is None:
            return
        if _is_state_filtered(ent_reg, new_state, old_state) or (
            entities_filter and not entities_filter(new_state.entity_id)
        ):
            return
        target(event)

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
            _forward_state_events_filtered,  # type: ignore[arg-type]
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


def _is_state_filtered(
    ent_reg: er.EntityRegistry, new_state: State, old_state: State
) -> bool:
    """Check if the logbook should filter a state.

    Used when we are in live mode to ensure
    we only get significant changes (state.last_changed != state.last_updated)
    """
    return bool(
        new_state.state == old_state.state
        or split_entity_id(new_state.entity_id)[0] in ALWAYS_CONTINUOUS_DOMAINS
        or new_state.last_changed != new_state.last_updated
        or ATTR_UNIT_OF_MEASUREMENT in new_state.attributes
        or is_sensor_continuous(ent_reg, new_state.entity_id)
    )


def _is_entity_id_filtered(
    hass: HomeAssistant, ent_reg: er.EntityRegistry, entity_id: str
) -> bool:
    """Check if the logbook should filter an entity.

    Used to setup listeners and which entities to select
    from the database when a list of entities is requested.
    """
    return bool(
        split_entity_id(entity_id)[0] in ALWAYS_CONTINUOUS_DOMAINS
        or (state := hass.states.get(entity_id))
        and (ATTR_UNIT_OF_MEASUREMENT in state.attributes)
        or is_sensor_continuous(ent_reg, entity_id)
    )
