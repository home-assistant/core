"""HA event flow."""

from collections.abc import Sequence
import logging
import uuid

import domika_ha_framework.database.core as database_core
from domika_ha_framework.errors import DomikaFrameworkBaseError
import domika_ha_framework.push_data.flow as push_data_flow
from domika_ha_framework.push_data.models import (
    DomikaPushDataCreate,
    DomikaPushedEvents,
)
import domika_ha_framework.subscription.flow as subscription_flow
from domika_ha_framework.utils import flatten_json

from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import (
    CompressedState,
    Event,
    EventStateChangedData,
    HomeAssistant,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    CRITICAL_PUSH_ALERT_STRINGS,
    LOGGER,
    PUSH_DELAY_DEFAULT,
    PUSH_DELAY_FOR_DOMAIN,
)
from ..critical_sensor import service as critical_sensor_service
from ..critical_sensor.enums import NotificationType


async def register_event(
    hass: HomeAssistant,
    event: Event[EventStateChangedData],
) -> None:
    """Register new incoming HA event."""
    event_data: EventStateChangedData = event.data

    entity_id = event_data["entity_id"]

    attributes = _get_changed_attributes_from_event_data(event_data)

    LOGGER.debug("Got event for entity: %s, attributes: %s", entity_id, attributes)

    if not attributes:
        return

    # Check if it's a critical or warning binary sensor.
    notification_required = critical_sensor_service.check_notification_type(
        hass,
        entity_id,
        NotificationType.ANY,
    )

    # Fire event for application if important sensor changed it's state.
    if notification_required:
        _fire_critical_sensor_notification(
            hass,
            event,
        )

    # Store events into db.
    event_id = uuid.uuid4()
    delay = await _get_delay_by_entity_id(hass, entity_id)
    events = [
        DomikaPushDataCreate(
            event_id=event_id,
            entity_id=entity_id,
            attribute=attribute[0],
            value=attribute[1],
            context_id=event.context.id,
            timestamp=int(event.time_fired.timestamp() * 1e6),
            delay=delay,
        )
        for attribute in attributes
    ]

    critical_push_needed = (
        critical_sensor_service.critical_push_needed(hass, entity_id)
        and ("s", "on") in attributes
    )

    critical_alert_payload = (
        _get_critical_alert_payload(hass, entity_id) if critical_push_needed else {}
    )

    try:
        async with database_core.get_session() as session:
            # Get application id's associated with attributes.
            app_session_ids = await subscription_flow.get_app_session_id_by_attributes(
                session,
                entity_id,
                [attribute[0] for attribute in attributes],
            )

            # If any app_session_ids are subscribed for these attributes - fire the event to those
            # app_session_ids for app to catch.
            if app_session_ids:
                _fire_event_to_app_session_ids(
                    hass,
                    event,
                    event_id,
                    entity_id,
                    attributes,
                    app_session_ids,
                )

            pushed_events = await push_data_flow.register_event(
                session,
                async_get_clientsession(hass),
                push_data=events,
                critical_push_needed=critical_push_needed,
                critical_alert_payload=critical_alert_payload,
            )
            if LOGGER.isEnabledFor(logging.DEBUG):
                _log_pushed_events(pushed_events)
    except DomikaFrameworkBaseError:
        LOGGER.exception(
            "Can't register event entity: %s attributes %s. Framework error",
            entity_id,
            attributes,
        )


def _get_critical_alert_payload(hass: HomeAssistant, entity_id: str) -> dict:
    """Create the payload for a critical push."""
    alert_title = CRITICAL_PUSH_ALERT_STRINGS.get("default", "")
    alert_body = hass.config.location_name

    entity = hass.states.get(entity_id)
    if entity:
        entity_class = entity.attributes.get(ATTR_DEVICE_CLASS)
        if entity_class:
            alert_title = CRITICAL_PUSH_ALERT_STRINGS.get(entity_class, "")

        alert_body = f"{entity.name}, " + alert_body

    return {"title-loc-key": alert_title, "body": alert_body}


async def push_registered_events(hass: HomeAssistant) -> None:
    """Push registered events to the push server."""
    async with database_core.get_session() as session:
        pushed_events = await push_data_flow.push_registered_events(
            session, async_get_clientsession(hass)
        )
        if LOGGER.isEnabledFor(logging.DEBUG):
            _log_pushed_events(pushed_events)


def _log_pushed_events(
    pushed_events: list[DomikaPushedEvents],
    max_events_msg_len: int = 1000,
) -> None:
    for pushed_event in pushed_events:
        attributes_count = 0
        for entity in pushed_event.events.values():
            attributes_count += len(entity)

        # Entities with their changed attributes.
        data = str(pushed_event.events)
        data = (
            data[:max_events_msg_len] + "..."
            if len(data) > max_events_msg_len
            else data
        )

        LOGGER.debug(
            "Pushed %s changed attributes in %s entities for %s push_session_id: %s",
            attributes_count,
            len(pushed_event.events),
            pushed_event.push_session_id,
            data,
        )


def _get_changed_attributes_from_event_data(event_data: EventStateChangedData) -> set:
    old_state: CompressedState | dict = {}
    if event_data["old_state"]:
        old_state = event_data["old_state"].as_compressed_state

    new_state: CompressedState | dict = {}
    if event_data["new_state"]:
        new_state = event_data["new_state"].as_compressed_state

    # Make a flat dict from state data.
    old_attributes = flatten_json(old_state, exclude={"c", "lc", "lu"}) or {}
    new_attributes = flatten_json(new_state, exclude={"c", "lc", "lu"}) or {}

    # Calculate the changed attributes by subtracting old_state elements from new_state.
    return set(new_attributes.items()) - set(old_attributes.items())


def _fire_critical_sensor_notification(
    hass: HomeAssistant,
    event: Event[EventStateChangedData],
) -> None:
    # If entity id is a critical binary sensor.
    # Fetch state for all levels of critical binary sensors.
    sensors_data = critical_sensor_service.get(hass, NotificationType.ANY)
    # Fire the event for app.
    hass.bus.async_fire(
        "domika_critical_sensors_changed",
        sensors_data.to_dict(),
        event.origin,
        event.context,
        event.time_fired.timestamp(),
    )


def _fire_event_to_app_session_ids(
    hass: HomeAssistant,
    event: Event[EventStateChangedData],
    event_id: uuid.UUID,
    entity_id: str,
    attributes: set[tuple],
    app_session_ids: Sequence[uuid.UUID],
) -> None:
    dict_attributes = dict(attributes)
    dict_attributes["d.type"] = "state_changed"
    dict_attributes["event_id"] = event_id
    dict_attributes["entity_id"] = entity_id
    for app_session_id in app_session_ids:
        hass.bus.async_fire(
            f"domika_{app_session_id}",
            dict_attributes,
            event.origin,
            event.context,
            event.time_fired.timestamp(),
        )


async def _get_delay_by_entity_id(hass: HomeAssistant, entity_id: str) -> int:
    """Get push notifications delay by entity id."""
    state = hass.states.get(entity_id)
    if not state:
        return PUSH_DELAY_DEFAULT

    return PUSH_DELAY_FOR_DOMAIN.get(state.domain, PUSH_DELAY_DEFAULT)
