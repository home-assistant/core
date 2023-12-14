"""Rasc helper."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import timedelta
import statistics
import time
from typing import Any, TypeVar

from homeassistant.const import (
    CONF_EVENT,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    RASC_COMPLETE,
    RASC_RESPONSE,
    RASC_START,
)
from homeassistant.core import Event, HomeAssistant

from .entity import Entity
from .template import device_entities

RT = TypeVar("RT")


def rasc_push_event(func: Callable[..., RT]) -> Callable[..., RT]:
    """RASC decorator for push-based devices."""

    def _wrapper(self: Entity, *args: Any, **kwargs: dict[str, Any]) -> RT:
        rt = func(self, *args, **kwargs)
        if self.async_on_push_event is not None:
            self.async_on_push_event(self)
        return rt

    return _wrapper


def get_statistics(
    hass: HomeAssistant, entity: Entity, action: str, transition: int
) -> tuple[float | None, float | None]:
    """Get action's statistics."""
    key = (entity.entity_id, action, transition)
    if key not in hass.rasc_global_state:
        return None, None
    if (
        "time_to_start" in hass.rasc_global_state[key]
        and len(hass.rasc_global_state[key]["time_to_start"]) > 0
    ):
        time_to_start = statistics.fmean(hass.rasc_global_state[key]["time_to_start"])
    else:
        time_to_start = None
    if (
        "time_to_complete" in hass.rasc_global_state[key]
        and len(hass.rasc_global_state[key]["time_to_complete"]) > 0
    ):
        time_to_complete = statistics.fmean(
            hass.rasc_global_state[key]["time_to_complete"]
        )
    else:
        time_to_complete = None
    return time_to_start, time_to_complete


def update_state(
    hass: HomeAssistant,
    entity: Entity,
    action: str,
    transition: int,
    time_to_start: float | None = None,
    time_to_complete: float | None = None,
) -> None:
    """Update rasc state."""
    key = (entity.entity_id, action, transition)
    if key not in hass.rasc_global_state:
        hass.rasc_global_state[key] = {"time_to_start": [], "time_to_complete": []}

    if time_to_start:
        hass.rasc_global_state[key]["time_to_start"].append(time_to_start)
    if time_to_complete:
        hass.rasc_global_state[key]["time_to_complete"].append(time_to_complete)


async def rasc_on_command(
    hass: HomeAssistant,
    e: Event,
    entities: Iterable[Entity],
    default_polling_interval: timedelta | None,
    rascal_state_map: dict[str, Any],
) -> timedelta | None:
    """Invoke when RASC receives an event."""
    target_entities = get_target_entities(hass, e, entities)
    polling_interval = default_polling_interval
    for target_entity in target_entities:
        rascal_state_map[target_entity.entity_id] = await async_get_rasc_state(
            hass, e, target_entity
        )
        _polling_interval = get_polling_interval(
            rascal_state_map[target_entity.entity_id]
        )
        if _polling_interval is None:
            continue
        if polling_interval is None or (_polling_interval < polling_interval):
            polling_interval = _polling_interval
    return polling_interval


def rasc_on_update(
    hass: HomeAssistant,
    default_polling_interval: timedelta | None,
    rascal_state_map: dict[str, Any],
) -> tuple[list[Entity], timedelta | None]:
    """Invoke when RASC updates the state."""
    completed_entities = update_rasc_state(hass, rascal_state_map)
    polling_interval = default_polling_interval
    for rasc_state in rascal_state_map.values():
        _polling_interval = get_polling_interval(rasc_state)
        if _polling_interval is None:
            continue
        if polling_interval is None or (_polling_interval < polling_interval):
            polling_interval = _polling_interval
    return completed_entities, polling_interval


def get_target_entities(
    hass: HomeAssistant, e: Event, own_entities: Iterable[Entity]
) -> Iterable[Entity]:
    """Get target entities from Event e."""
    entities: list[str] = []
    if "device_id" in e.data["service_data"]:
        entities = entities + [
            entity
            for _device_id in e.data["service_data"]["device_id"]
            for entity in device_entities(hass, _device_id)
        ]
    if "entity_id" in e.data["service_data"]:
        if isinstance(e.data["service_data"]["entity_id"], str):
            entities = entities + [e.data["service_data"]["entity_id"]]
        else:
            entities = entities + e.data["service_data"]["entity_id"]

    return [entity for entity in own_entities if entity.entity_id in entities]


async def async_get_rasc_state(
    hass: HomeAssistant, e: Event, entity: Entity
) -> dict[str, Any]:
    """Get RASC state on the given Event e."""
    time_to_start, time_to_complete = get_statistics(
        hass, entity, e.data[CONF_SERVICE], e.data["service_data"].get("transition", 0)
    )
    start_state = await entity.async_get_action_target_state(
        {
            CONF_EVENT: RASC_START,
            CONF_SERVICE: e.data[CONF_SERVICE],
            CONF_SERVICE_DATA: e.data["service_data"],
        }
    )
    complete_state = await entity.async_get_action_target_state(
        {
            CONF_EVENT: RASC_COMPLETE,
            CONF_SERVICE: e.data[CONF_SERVICE],
            CONF_SERVICE_DATA: e.data["service_data"],
        }
    )
    return {
        "next_response": RASC_START,
        "start_state": start_state,
        "complete_state": complete_state,
        "exec_time": time.time(),
        "time_left_to_start": time_to_start or 1,
        "time_left_to_complete": time_to_complete
        or e.data["service_data"].get("transition", 0),
        # original attrs
        "context": e.context,
        CONF_SERVICE: e.data[CONF_SERVICE],
        "service_data": e.data["service_data"],
        "entity": entity,
    }


def update_rasc_state(
    hass: HomeAssistant,
    rascal_state_map: dict[str, Any],
    entity: Entity | None = None,
) -> list[Entity]:
    """Update RASC and fire responses if any."""
    completed_list: list[Entity] = []
    for entity_id, state in list(rascal_state_map.items()):
        if entity and entity.entity_id != entity_id:
            continue

        # update time_left_to_start, time_left_to_complete
        if state["next_response"] == RASC_START:
            state["time_left_to_start"] = state["time_left_to_start"] - (
                time.time() - state["exec_time"]
            )
            if state["time_left_to_start"] < 1:
                state["time_left_to_start"] = 1
        elif state["next_response"] == RASC_COMPLETE:
            state["time_left_to_complete"] = state["time_left_to_complete"] - (
                time.time() - state["exec_time"]
            )
            if state["time_left_to_complete"] < 1:
                state["time_left_to_complete"] = 1

        complete_state_matched = True
        for attr, match in state["complete_state"].items():
            if not match(getattr(entity or state["entity"], attr)):
                complete_state_matched = False
                break
        # prevent hazardous changes
        transition = state["service_data"].get("transition", None)
        if complete_state_matched and (
            transition is None or time.time() - state["exec_time"] > transition / 2
        ):
            if state["next_response"] == RASC_START:
                print("fire", RASC_START, "response:", entity_id)  # noqa: T201
                hass.bus.async_fire(
                    RASC_RESPONSE,
                    {"type": RASC_START, "entity_id": entity_id},
                )
            print("fire", RASC_COMPLETE, "response:", entity_id)  # noqa: T201
            hass.bus.async_fire(
                RASC_RESPONSE,
                {"type": RASC_COMPLETE, "entity_id": entity_id},
            )
            time_to_complete = time.time() - state["exec_time"]
            update_state(
                hass,
                entity or state["entity"],
                state[CONF_SERVICE],
                state["service_data"].get("transition", 0),
                time_to_complete=time_to_complete,
            )

            completed_list.append(entity or state["entity"])
            del rascal_state_map[entity_id]
            continue

        start_state_matched = True
        for attr, match in state["start_state"].items():
            if not match(getattr(entity or state["entity"], attr)):
                start_state_matched = False
                break
        if start_state_matched and state["next_response"] == RASC_START:
            print("fire", RASC_START, "response:", entity_id)  # noqa: T201
            hass.bus.async_fire(
                RASC_RESPONSE,
                {"type": state["next_response"], "entity_id": entity_id},
            )
            state["next_response"] = RASC_COMPLETE
            time_to_start = time.time() - state["exec_time"]
            update_state(
                hass,
                entity or state["entity"],
                state[CONF_SERVICE],
                state["service_data"].get("transition", 0),
                time_to_start=time_to_start,
            )
    return completed_list


def get_polling_interval(rasc_state: dict[str, Any]) -> timedelta | None:
    """Get polling interval based on current rasc state."""
    if rasc_state["next_response"] == RASC_START:
        return timedelta(seconds=max(1, round(rasc_state["time_left_to_start"] / 2)))
    if rasc_state["next_response"] == RASC_COMPLETE:
        return timedelta(seconds=max(1, round(rasc_state["time_left_to_complete"] / 2)))
    return None
