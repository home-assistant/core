"""Support for rasc."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Sequence
import copy
from datetime import datetime, timedelta
import json
import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from homeassistant.const import (
    ATTR_ACTION_ID,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_PARALLEL,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    CONF_TARGET,
    CONF_TYPE,
    DOMAIN_SCRIPT,
    FCFS,
    FCFS_POST,
    JIT,
    LOCK_STATE_ACQUIRED,
    LOCK_STATE_LEASED,
    LOCK_STATE_RELEASED,
    LOCK_STATE_SCHEDULED,
    RASC_ACK,
    RASC_COMPLETE,
    RASC_RESPONSE,
    RASC_SCHEDULED,
    RASC_START,
    SCHEDULING_POLICY,
    TIMELINE,
)
from homeassistant.core import Event, HomeAssistant

if TYPE_CHECKING:
    from homeassistant.components.script import BaseScriptEntity
    from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.helpers.rascalscheduler import (
    datetime_to_string,
    generate_duration,
    get_routine_id,
    string_to_datetime,
)
from homeassistant.helpers.template import device_entities
from homeassistant.helpers.typing import ConfigType

from .abstraction import RASCAbstraction
from .const import ACTION_LENGTH_PADDING, CONF_TRANSITION, DOMAIN
from .entity import (
    ActionEntity,
    BaseRoutineEntity,
    Queue,
    RoutineEntity,
    get_entity_id_from_number,
)
from .log import LOG_PATH, TRAIL, set_logger
from .metrics import ScheduleMetrics

CONF_ROUTINE_ID = "routine_id"
CONF_STEP = "step"
CONF_END_VIRTUAL_NODE = "end_virtual_node"

TIMEOUT = 3000  # millisecond

_LOGGER = set_logger()


def create_routine(
    hass: HomeAssistant,
    name: str | None,
    routine_id: str,
    action_script: Sequence[dict[str, Any]],
) -> BaseRoutineEntity:
    """Create a routine based on the given action script."""
    rasc: Optional[RASCAbstraction] = hass.data[DOMAIN]
    if not rasc:
        raise ValueError("RASC is not initialized.")
    next_parents: list[ActionEntity] = []
    entities: dict[str, ActionEntity] = {}
    config: dict[str, Any] = {}

    # confige action id for each node
    config[CONF_STEP] = -1
    config[CONF_ROUTINE_ID] = routine_id

    for _, script in enumerate(action_script):
        if (
            CONF_PARALLEL not in script
            and CONF_SEQUENCE not in script
            and CONF_SERVICE not in script
            and CONF_DELAY not in script
        ):
            # print("script:", script)
            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
            action: str = script[CONF_TYPE]
            if CONF_TRANSITION in script:
                transition: float | None = script[CONF_TRANSITION]
                _LOGGER.debug(
                    "The transition of action %s is %f", action_id, transition
                )
            else:
                transition = None
            target_entities = get_target_entities(hass, script)
            estimated_duration = dict[str, timedelta]()
            for entity in target_entities:
                entity_id = get_entity_id_from_number(hass, entity)
                estimated_entity_duration = (
                    rasc.get_action_length_estimate(
                        entity_id, action=action, transition=transition
                    )
                    + ACTION_LENGTH_PADDING
                )
                estimated_duration[entity_id] = generate_duration(
                    estimated_entity_duration
                )

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                duration=estimated_duration,
                logger=_LOGGER,
            )

            for parent in next_parents:
                entities[action_id].parents.append(parent)

            for parent in next_parents:
                parent.children.append(entities[action_id])

            next_parents.clear()
            next_parents.append(entities[action_id])

        else:
            leaf_nodes = _create_routine(hass, script, config, next_parents, entities)
            next_parents.clear()
            next_parents = leaf_nodes

    # add virtual node to the end of the routine
    # the use of the virtual node is to identify if all actions in the routine are completed
    entities[CONF_END_VIRTUAL_NODE] = ActionEntity(
        hass=hass,
        action={},
        action_id="",
        duration={},
        is_end_node=True,
        logger=_LOGGER,
    )

    for parent in next_parents:
        parent.children.append(entities[CONF_END_VIRTUAL_NODE])
        entities[CONF_END_VIRTUAL_NODE].parents.append(parent)

    return BaseRoutineEntity(name, routine_id, entities, action_script)


def _create_routine(
    hass: HomeAssistant,
    script: dict[str, Any],
    config: dict[str, Any],
    parents: list[ActionEntity],
    entities: dict[str, ActionEntity],
) -> list[ActionEntity]:
    """Create a routine based on the given action script."""
    rasc: Optional[RASCAbstraction] = hass.data[DOMAIN]
    if not rasc:
        raise ValueError("RASC is not initialized.")

    next_parents: list[ActionEntity] = []
    # print("script:", script)
    if CONF_PARALLEL in script:
        for item in list(script.values())[0]:
            leaf_entities = _create_routine(hass, item, config, parents, entities)
            for entity in leaf_entities:
                next_parents.append(entity)

    elif CONF_SEQUENCE in script:
        next_parents = parents
        for item in list(script.values())[0]:
            leaf_entities = _create_routine(hass, item, config, next_parents, entities)
            next_parents = leaf_entities

    elif CONF_SERVICE in script:
        domain: str = script[CONF_SERVICE].split(".")[0]
        if domain == DOMAIN_SCRIPT:
            script_component: EntityComponent[BaseScriptEntity] = hass.data[
                DOMAIN_SCRIPT
            ]

            if script_component:
                base_script = script_component.get_entity(list(script.values())[0])
                if base_script and base_script.raw_config:
                    next_parents = parents
                    for item in base_script.raw_config[CONF_SEQUENCE]:
                        leaf_entities = _create_routine(
                            hass, item, config, next_parents, entities
                        )
                        next_parents = leaf_entities
        else:
            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
            action: str = script[CONF_SERVICE]
            if (
                CONF_SERVICE_DATA in script
                and CONF_TRANSITION in script[CONF_SERVICE_DATA]
            ):
                transition: float | None = script[CONF_SERVICE_DATA][CONF_TRANSITION]
                _LOGGER.debug(
                    "The transition of action %s is %f", action_id, transition
                )
            else:
                transition = None
            target_entities = get_target_entities(hass, script)
            estimated_duration = dict[str, timedelta]()
            for target_entity in target_entities:
                entity_id = get_entity_id_from_number(hass, target_entity)
                estimated_entity_duration = (
                    rasc.get_action_length_estimate(
                        entity_id, action=action, transition=transition
                    )
                    + ACTION_LENGTH_PADDING
                )
                estimated_duration[entity_id] = generate_duration(
                    estimated_entity_duration
                )

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                duration=estimated_duration,
                logger=_LOGGER,
            )

            for parent in parents:
                entities[action_id].parents.append(parent)
                parent.children.append(entities[action_id])

            next_parents.append(entities[action_id])

    elif CONF_DELAY in script:
        hours = script[CONF_DELAY]["hours"]
        minutes = script[CONF_DELAY]["minutes"]
        seconds = script[CONF_DELAY]["seconds"]
        milliseconds = script[CONF_DELAY]["milliseconds"]

        delta = timedelta(
            hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
        )

        for parent in parents:
            parent.delay = delta

        next_parents = parents

    else:
        config[CONF_STEP] = config[CONF_STEP] + 1
        action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
        action = script[CONF_TYPE]
        if CONF_TRANSITION in script:
            transition = script[CONF_TRANSITION]
            _LOGGER.debug("The transition of action %s is %f", action_id, transition)
        else:
            transition = None
        target_entities = get_target_entities(hass, script)
        estimated_duration = dict[str, timedelta]()
        for target_entity in target_entities:
            entity_id = get_entity_id_from_number(hass, target_entity)
            estimated_entity_duration = (
                rasc.get_action_length_estimate(
                    entity_id, action=action, transition=transition
                )
                + ACTION_LENGTH_PADDING
            )
            estimated_duration[entity_id] = generate_duration(estimated_entity_duration)

        entities[action_id] = ActionEntity(
            hass=hass,
            action=script,
            action_id=action_id,
            duration=estimated_duration,
            logger=_LOGGER,
        )

        for parent in parents:
            entities[action_id].parents.append(parent)
            parent.children.append(entities[action_id])

        next_parents.append(entities[action_id])

    return next_parents


def get_target_entities(hass: HomeAssistant, script: dict[str, Any]) -> list[str]:
    """Get all the entities from the given script."""
    target_entities: list[str] = []

    # print("script:", script)
    if CONF_SERVICE in script:
        if CONF_DEVICE_ID in script[CONF_TARGET]:
            device_ids = []
            if isinstance(script[CONF_TARGET][CONF_DEVICE_ID], str):
                device_ids = [script[CONF_TARGET][CONF_DEVICE_ID]]
            else:
                device_ids = script[CONF_TARGET][CONF_DEVICE_ID]
            target_entities += [
                get_entity_id_from_number(hass, entity)
                for device_id in device_ids
                for entity in device_entities(hass, device_id)
            ]

        if CONF_ENTITY_ID in script[CONF_TARGET]:
            if isinstance(script[CONF_TARGET][CONF_ENTITY_ID], str):
                target_entities += [
                    get_entity_id_from_number(hass, script[CONF_TARGET][CONF_ENTITY_ID])
                ]
            else:
                target_entities += [
                    get_entity_id_from_number(hass, entity)
                    for entity in script[CONF_TARGET][CONF_ENTITY_ID]
                ]
    else:
        target_entities = [get_entity_id_from_number(hass, script[CONF_ENTITY_ID])]

    return target_entities


def output_lock_queues(
    lock_queues: dict[str, Queue[str, ActionInfo]], filepath: Optional[str] = None
) -> None:
    """Output the lock queues."""
    if filepath:
        fp = os.path.join(filepath, "locks_queues.json")
    lock_queues_list = []
    for entity_id, actions in lock_queues.items():
        action_list = []
        for action_id, action_info in actions.items():
            if action_info:
                sub_entity_json = {
                    "action_id": action_id,
                    "action_state": action_info.action_state,
                    "lock_state": action_info.lock_state,
                    "start_time": action_info.time_range[0],
                    "end_time": action_info.time_range[1],
                }
                action_list.append(sub_entity_json)

        entity_json = {"entity_id": entity_id, "actions": action_list}

        lock_queues_list.append(entity_json)

    out = {"Type": "Lock Queues", "Lock Queues": lock_queues_list}
    if filepath:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    else:
        _LOGGER.debug(json.dumps(out, indent=2))


def output_locks(locks: dict[str, str | None], filepath: str) -> None:
    """Output the locks."""
    fp = os.path.join(filepath, "locks.json")

    locks_list = []
    for entity_id, routine_id in locks.items():
        entity_json = {"entity_id": entity_id, "routine_id": routine_id}
        locks_list.append(entity_json)

    out = {"Type": "Locks", "Locks": locks_list}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201


def output_wait_queues(wait_queue: Queue[str, WaitRoutineInfo], filepath: str) -> None:
    """Output wait queues."""
    fp = os.path.join(filepath, "wait_queue.json")
    routines: list[str] = []
    for routine_id in wait_queue:
        routines.append(routine_id)

    out = {"Type": "Wait Queue", "Wait Queue": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201


def output_lock_waitlist(lock_waitlist: dict[str, list[str]], filepath: str) -> None:
    """Output lock waitlist."""
    fp = os.path.join(filepath, "lock_waitlist.json")

    waitlist = []
    for entity_id, routines in lock_waitlist.items():
        routine_list = []
        for routine_id in routines:
            routine_list.append(routine_id)

        entity_json = {"entity_id": entity_id, "waitlist": routine_list}

        waitlist.append(entity_json)

    out = {"Type": "Lock Waitlist", "Routines": waitlist}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def output_serialization_order(
    serialization_order: Queue[str, RoutineInfo], filepath: str
) -> None:
    """Output serialization order."""
    fp = os.path.join(filepath, "serialization_order.json")
    routines: list[str] = []
    for routine_id in serialization_order:
        routines.append(routine_id)

    out = {"Type": "Serialization Order", "Serialization Order": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    # print(json.dumps(out, indent=2))  # noqa: T201()


def output_free_slots(
    timelines: dict[str, Queue[str, str]], filepath: Optional[str] = None
) -> None:
    """Output free slots."""
    if filepath:
        fp = os.path.join(filepath, "free_slots.json")

    tl = []
    for entity_id, timeline in timelines.items():
        slot_list: list[dict[str, str | None]] = []
        for st, end in timeline.items():
            sub_entity_json: dict[str, str | None] = {"st": st, "end": end}

            slot_list.append(sub_entity_json)

        entity_json = {"entity_id": entity_id, "timeline": slot_list}

        tl.append(entity_json)

    out = {"Type": "Free Slots", "Free Slots": tl}
    if filepath:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    else:
        _LOGGER.debug(json.dumps(out, indent=2))


def output_routine(routine_id: str, actions: dict[str, ActionEntity]) -> None:
    """Output routine."""
    dirname = f"trail-{TRAIL.num:04d}"
    TRAIL.increment()

    os.path.join(LOG_PATH, dirname, "routines.json")

    action_list = []
    for _, entity in actions.items():
        parents = []
        children = []

        for parent in entity.parents:
            parents.append(parent.action_id)

        for child in entity.children:
            children.append(child.action_id)

        entity_json = {
            "action_id": entity.action_id,
            "action": entity.action,
            "action_completed": entity.action_completed,
            "parents": parents,
            "children": children,
            "delay": str(entity.delay),
            "duration": str(entity.duration),
        }

        action_list.append(entity_json)

    out = {"Routine_id": routine_id, "Actions": action_list}

    print(json.dumps(out, indent=2))  # noqa: T201


def output_preset(preset: set[str], filepath: str) -> None:
    """Output serialization order."""
    fp = os.path.join(filepath, "preset.json")
    routines: list[str] = []
    for routine_id in preset:
        routines.append(routine_id)

    out = {"Type": "Preset", "Routines": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def output_postset(postset: set[str], filepath: str) -> None:
    """Output serialization order."""
    fp = os.path.join(filepath, "postset.json")
    routines: list[str] = []
    for routine_id in postset:
        routines.append(routine_id)

    out = {"Type": "Postset", "Routines": routines}
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def output_all(
    logger: logging.Logger,
    locks: dict[str, str | None] | None = None,
    lock_queues: dict[str, Queue[str, ActionInfo]] | None = None,
    free_slots: dict[str, Queue[str, str]] | None = None,
    serialization_order: Queue[str, RoutineInfo] | None = None,
    wait_queue: Queue[str, WaitRoutineInfo] | None = None,
    lock_waitlist: dict[str, list[str]] | None = None,
    preset: set[str] | None = None,
    postset: set[str] | None = None,
):
    """Output specific info."""

    dirname = f"trail-{TRAIL.num:04d}"
    TRAIL.increment()

    fp = os.path.join(LOG_PATH, dirname)
    logger.debug("Output logs to %s.", fp)

    if not os.path.isdir(fp):
        os.mkdir(fp)

    if locks:
        output_locks(locks, fp)

    if lock_queues:
        output_lock_queues(lock_queues, fp)

    if free_slots:
        output_free_slots(free_slots, fp)

    if serialization_order:
        output_serialization_order(serialization_order, fp)

    if wait_queue:
        output_wait_queues(wait_queue, fp)

    if lock_waitlist:
        output_lock_waitlist(lock_waitlist, fp)

    if preset:
        output_preset(preset, fp)

    if postset:
        output_postset(postset, fp)


class ActionInfo:
    """A class for storing information about a scheduled action in the lock queues."""

    def __init__(
        self,
        action_id: str,
        action: ActionEntity,
        action_state: str,
        lock_state: str,
        start_time: str,
        end_time: str,
    ) -> None:
        """Initialize the action info."""
        self._action_id = action_id
        self._action = action
        self.action_state = action_state
        self.lock_state = lock_state
        self._start_time = start_time
        self._end_time = end_time

    @property
    def action_id(self) -> str:
        """Get action id."""
        return self._action_id

    @property
    def action(self) -> ActionEntity:
        """Get action."""
        return self._action

    @property
    def start_time(self) -> str:
        """Get start time."""
        return self._start_time

    @property
    def end_time(self) -> str:
        """Get end time."""
        return self._end_time

    @property
    def time_range(self) -> tuple[str, str]:
        """Get time range."""
        return (self._start_time, self._end_time)

    @property
    def duration(self) -> timedelta:
        """Get duration."""
        return string_to_datetime(self._end_time) - string_to_datetime(self._start_time)

    def move_to(self, new_start_time: str, new_end_time: str) -> None:
        """Move to new time range."""
        self._start_time = new_start_time
        self._end_time = new_end_time


class RoutineInfo:
    """A class for storing information about a scheduled routine in the serialization order."""

    def __init__(
        self,
        routine_id: str,
        routine: RoutineEntity,
    ) -> None:
        """Initialize the routine info."""
        self._routine_id = routine_id
        self.routine = routine
        self.pass_eligibility: bool = False

    @property
    def routine_id(self) -> str:
        """Get routine id."""
        return self._routine_id


class WaitRoutineInfo:
    """A class for storing information about a waiting routine in the wait queue."""

    def __init__(
        self,
        routine_id: str,
        routine: RoutineEntity,
        ttl: int = 4,  # to avoid starvation
    ) -> None:
        """Initialize the wait routine info."""
        self._routine_id = routine_id
        self.routine = routine
        self.ttl = ttl

    @property
    def routine_id(self) -> str:
        """Get routine id."""
        return self._routine_id


class LineageTable:
    """Maintains a per-device lineage: the planned transition order of that device's lock.

    locks: the state of the device's lock.
    lock_queues: transition order of the device's lock.
    free slots: a list of available time slots in chronological order.

    """

    def __init__(self, lt: LineageTable | None = None) -> None:
        """Initialize linage table entity."""

        # locks: key is the entity_id and value is the routine id that is holding the
        # lock now, if any routine is
        self._locks: dict[str, str | None] = {}

        # lock_queues: key is the entity_id and each element stored in the queue is the
        # (action id, action lock info) tuple that is holding or waiting for the lock
        self._lock_queues: dict[str, Queue[str, ActionInfo]] = {}
        if lt:
            for entity_id, lock_queue in lt.lock_queues.items():
                self._lock_queues[entity_id] = Queue[str, ActionInfo](
                    {
                        action_id: copy.deepcopy(action_lock)
                        for action_id, action_lock in lock_queue.items()
                    }
                )

        # free_slots: key is the entity_id and each element stored in the queue is a
        # slot where the start time is the key and the end time is the value
        self._free_slots: dict[str, Queue[str, str]] = {}
        if lt:
            self._free_slots = copy.deepcopy(lt.free_slots)

    @property
    def locks(self) -> dict[str, str | None]:
        """Get locks."""
        return self._locks

    @locks.setter
    def locks(self, new_locks: dict[str, str | None]) -> None:
        """Set locks."""
        self._locks = new_locks

    @property
    def lock_queues(self) -> dict[str, Queue[str, ActionInfo]]:
        """Get lock queues."""
        return self._lock_queues

    @lock_queues.setter
    def lock_queues(self, new_lock_queues: dict[str, Queue]) -> None:
        """Set lock queues."""
        self._lock_queues = new_lock_queues

    @property
    def free_slots(self) -> dict[str, Queue[str, str]]:
        """Get free slots."""
        return self._free_slots

    @free_slots.setter
    def free_slots(self, fs: dict[str, Queue[str, str]]) -> None:
        """Set free slots."""
        self._free_slots = fs

    def add_entity(self, entity_id: str) -> None:
        """Add the entity to the lineage table."""
        self._locks[entity_id] = None
        self._lock_queues[entity_id] = Queue[str, ActionInfo]()
        self._free_slots[entity_id] = Queue[str, str](
            {datetime_to_string(datetime.now()): None}
        )

    def delete_entity(self, entity_id: str) -> None:
        """Remove the entity with the entity_id from the lineage table."""
        try:
            del self._lock_queues[entity_id]
            del self._locks[entity_id]
            del self._free_slots[entity_id]
        except KeyError as e:
            raise KeyError(f"While deleting entity {entity_id} in lineage table") from e


class BaseScheduler:
    """A class for base scheduler."""

    _hass: HomeAssistant
    _serialization_order: Queue[str, RoutineInfo]
    _lineage_table: LineageTable
    _scheduling_policy: str

    def get_action(self, action_id: str) -> ActionEntity | None:
        """Get the active action."""
        routine_info = self._serialization_order[get_routine_id(action_id)]

        if not routine_info:
            return None

        return routine_info.routine.actions[action_id]

    def filter_ts(
        self, entity_id: str, now: datetime, free_slots: dict[str, Queue[str, str]]
    ) -> Queue[str, str]:
        """Filter the time slots of the entity that the end time is not smaller than now."""

        fs: Queue = free_slots[entity_id]

        if not fs:
            raise ValueError(
                "There should be at least one time slot in each entity's timeline"
            )

        filtered_time_slots: Queue[str, str] = Queue[str, str]()
        for start_time, end_time in fs.items():
            if not end_time or end_time > datetime_to_string(now):
                filtered_time_slots[start_time] = end_time

        return filtered_time_slots

    def remove_time_slots_before_now(
        self, now: datetime, free_slots: dict[str, Queue[str, str]]
    ) -> None:
        """Remove all available time slots that have ended before now."""
        for entity_id, _ in free_slots.items():
            filtered_time_slots = self.filter_ts(entity_id, now, free_slots)
            start_time, end_time = filtered_time_slots.top()

            if not start_time:
                continue

            # Check if the start time of the first time slot needs to be updated
            if datetime_to_string(now) > start_time:
                filtered_time_slots.insert_after(
                    start_time, datetime_to_string(now), end_time
                )
                filtered_time_slots.pop(start_time)

            free_slots[entity_id] = Queue(filtered_time_slots)

        _LOGGER.debug(
            "Remove time slots that are smaller than the time %s",
            datetime_to_string(now),
        )

    def get_first_action_with_acquired_lock(self, entity_id: str) -> ActionInfo | None:
        """Get the first action with the lock."""
        lock_queue: Queue = self._lineage_table.lock_queues[entity_id]

        return (
            next(
                (
                    action_info
                    for action_info in lock_queue.values()
                    if action_info is not None
                    and action_info.lock_state == LOCK_STATE_ACQUIRED
                ),
                None,
            )
            if lock_queue
            else None
        )

    def get_last_action_with_acquired_lock(self, entity_id: str) -> ActionInfo | None:
        """Get the last action with lock."""
        lock_queue = self._lineage_table.lock_queues[entity_id]
        return (
            next(
                (
                    action_info
                    for action_info in reversed(list(lock_queue.values()))
                    if action_info is not None
                    and action_info.lock_state == LOCK_STATE_ACQUIRED
                ),
                None,
            )
            if lock_queue
            else None
        )

    def get_available_ts(
        self,
        now: datetime,
        free_slots: dict[str, Queue[str, str]],
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get the start time of the first available time slot for the given the entity."""

        if self._scheduling_policy == FCFS:
            start_time = self.get_available_ts_by_fcfs(
                free_slots, now, entity_id, lock_leasing_status, new_action
            )

        elif self._scheduling_policy == FCFS_POST:
            start_time = self.get_available_ts_by_fcfs_post(
                free_slots, now, entity_id, lock_leasing_status, new_action
            )

        elif self._scheduling_policy == JIT:
            start_time = self.get_available_ts_by_jit(
                free_slots, now, entity_id, lock_leasing_status, new_action
            )

        _LOGGER.debug(
            "The start time of the new time slot for the action %s in the entity %s is %s",
            new_action.action_id,
            entity_id,
            start_time,
        )

        return start_time

    def get_available_ts_by_fcfs(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get available time slot by fcfs."""
        # 1. Check if there is an action accessing the entity
        return self.get_ts_by_nolease(
            free_slots, now, entity_id, lock_leasing_status, new_action
        )

    def get_available_ts_by_fcfs_post(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get available time slot by fcfs_post."""

        # 1. Check if there is an action accessing the entity
        start_time = self.get_ts_by_nolease(
            free_slots, now, entity_id, lock_leasing_status, new_action
        )
        if start_time:
            return start_time

        # 2. Check if there is an action being able to post lease the lock
        return self.get_ts_by_postlease(
            free_slots, now, entity_id, lock_leasing_status, new_action
        )

    def get_available_ts_by_jit(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get available time slot by jit."""

        # 1. Check if there is an action accessing the entity
        start_time = self.get_ts_by_nolease(
            free_slots, now, entity_id, lock_leasing_status, new_action
        )
        if start_time:
            return start_time

        # 2. Check if there is an action being able to pre lease the lock
        start_time = self.get_ts_by_prelease(
            free_slots, now, entity_id, lock_leasing_status, new_action
        )
        if start_time:
            return start_time

        # 3. Check if there is an action being able to post lease the lock
        return self.get_ts_by_postlease(
            free_slots, now, entity_id, lock_leasing_status, new_action
        )

    def get_ts_by_nolease(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get the available time slot for the given entity by checking if the lock is available."""
        action: ActionInfo | None = self.get_first_action_with_acquired_lock(entity_id)
        return free_slots[entity_id].end()[0] if not action else None

    def get_ts_by_prelease(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get the next available time slot for the given entity by checking if the new action can get the lock by pre-lease."""
        action = self.get_first_action_with_acquired_lock(entity_id)

        if not action:
            raise ValueError(
                "Failed to prelease the lock. This shouldn't happen. There is at lease one action acquiring the lock now"
            )

        # Check if there is an available time slot before the action
        slot_start = self.find_ts_before_action(action, free_slots[entity_id], now)
        slot_end = free_slots[entity_id].get(slot_start) if slot_start else None

        if not slot_start or not slot_end:
            _LOGGER.error(
                "Failed to prelease the lock. Cannot find a slot before the action"
            )
            return None

        # Check if the slot is big enough to place the action
        if (
            string_to_datetime(slot_end)
            - string_to_datetime(max(slot_start, datetime_to_string(now)))
        ).total_seconds() < new_action.duration[entity_id].total_seconds():
            _LOGGER.error(
                "Failed to prelease the lock. The slot is too small to place the action"
            )
            return None

        # Check if the serializability conflicts if the new action places before the action.
        if self.conflict_serializability_by_prelease(action, entity_id):
            _LOGGER.error(
                "Failed to prelease the lock. Violate serializability while placing before the action %s",
                action.action_id,
            )
            return None

        # Check if the determined serializability conflicts if the new action places before the action.
        if self.conflict_determined_serializability(action, "pre", lock_leasing_status):
            _LOGGER.error(
                "Violate determined serializability. Failed to prelease the lock"
            )
            return None

        # Check if the action with the acquired key is running
        if self.action_running(action, entity_id, "pre"):
            _LOGGER.error("Failed to prelease the lock. The action is running")
            return None

        return slot_start

    def find_ts_before_action(
        self, action: ActionInfo, free_slots: Queue[str, str], now: datetime
    ) -> str | None:
        """Get the time slot before the given action."""
        action_st = action.start_time
        return next(
            (
                st
                for st, end in free_slots.items()
                if end == action_st and end > datetime_to_string(now)
            ),
            None,
        )

    def get_ts_by_postlease(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get the time slot after the given action."""

        action: ActionInfo | None = self.get_last_action_with_acquired_lock(entity_id)

        if not action:
            raise ValueError(
                "Failed to postlease the lock. This shouldn't happen. There is at lease one action acquiring the lock now"
            )

        # Check if the serializability would conflict if post-lease
        if self.conflict_serializability_by_postlease(action, entity_id, new_action):
            _LOGGER.error(
                "Failed to postlease the lock. Violate seriailzability while placing after the action %s",
                action.action_id,
            )
            return None

        # Check if the determined serializability conflicts if the new action places after the action.
        if self.conflict_determined_serializability(
            action, "post", lock_leasing_status
        ):
            _LOGGER.debug(
                "Failed to postlease the lock. Violate determined serializability"
            )
            return None

        # Check if the action with the acquired key is running
        if not self.action_running(action, entity_id, "post"):
            _LOGGER.error(
                "The action %s is not running. Failed to postlease the lock",
                action.action_id,
            )
            return None

        # find the available time slot at the end
        slot_start = free_slots[entity_id].end()[0]

        return slot_start

    def conflict_serializability_by_prelease(
        self, action: ActionInfo, entity_id: str
    ) -> bool:
        """Check if the serializability conflicts if the new action places before the action."""
        prev_action = self._lineage_table.lock_queues[entity_id].prev(action.action_id)

        if not prev_action:
            return False

        if prev_action.lock_state == LOCK_STATE_RELEASED:
            return False

        return True
        # return prev_action and prev_action.lock_state != LOCK_STATE_RELEASED

    def conflict_serializability_by_postlease(
        self, action: ActionInfo, entity_id: str, new_action: ActionEntity
    ) -> bool:
        """Check if the serializability conflicts if the new action places after the action."""
        next_action = self._lineage_table.lock_queues[entity_id].next(action.action_id)

        return bool(
            next_action
            and get_routine_id(next_action.action_id)
            != get_routine_id(new_action.action_id)
        )

        # return (
        #     True
        #     if next_action
        #     and get_routine_id(next_action.action_id)
        #     != get_routine_id(new_action.action_id)
        #     else False
        # )

    def conflict_determined_serializability(
        self,
        action: ActionInfo,
        lock_leasing: str,
        lock_leasing_status: dict[str, str],
    ) -> bool:
        """Check if the determined serializability conflicts if the new action places before the action."""

        idx1 = self._serialization_order.index(get_routine_id(action.action_id))

        for routine_id, lease_status in lock_leasing_status.items():
            idx2 = self._serialization_order.index(routine_id)

            if (lock_leasing == "pre" and lease_status == "post" and idx1 <= idx2) or (
                lock_leasing == "post" and lease_status == "pre" and idx1 >= idx2
            ):
                return True

        lock_leasing_status[get_routine_id(action.action_id)] = lock_leasing
        return False

    def action_running(
        self, action: ActionInfo, entity_id: str, lock_leasing: str
    ) -> bool:
        """Check if action is running."""
        if not action.action_id:
            return False

        action_info = self._lineage_table.lock_queues[entity_id].get(action.action_id)

        if not action_info:
            return False

        if lock_leasing == "pre" and action_info:
            return action_info.action_state in (RASC_ACK, RASC_START, RASC_COMPLETE)

        if action_info:
            return action_info.action_state in (RASC_START, RASC_COMPLETE)

        return False

    def schedule_action(
        self,
        slot: tuple[str, str | None],
        action_slot: tuple[str, str],
        free_slots: Queue[str, str],
    ) -> str:
        """Insert the action to the current time slot and then return the expected end time of the new action."""
        slot_st, slot_end = slot
        action_st, action_end = action_slot

        dt_slot_st = string_to_datetime(slot_st)
        dt_slot_end = string_to_datetime(slot_end) if slot_end else None
        dt_action_st = string_to_datetime(action_st)
        dt_action_end = string_to_datetime(action_end)

        if dt_slot_end:
            _LOGGER.debug(
                "Schedule action (%s, %s) to (%s, %s)",
                datetime_to_string(dt_action_st),
                datetime_to_string(dt_action_end),
                datetime_to_string(dt_slot_st),
                datetime_to_string(dt_slot_end),
            )
        else:
            _LOGGER.debug(
                "Schedule action (%s, %s) to (%s, %s)",
                datetime_to_string(dt_action_st),
                datetime_to_string(dt_action_end),
                datetime_to_string(dt_slot_st),
                dt_slot_end,
            )

        # To avoid many fragmentations
        # start_offset = (dt_new_slot_st - dt_slot_st).total_seconds() >= TIMELINE_UNIT
        # end_offset = (dt_slot_end - dt_new_slot_end).total_seconds() >= TIMELINE_UNIT if  dt_slot_end else True
        # _LOGGER.info("Insert time slot: start_offset: %s end_offset: %s", start_offset, end_offset)

        if slot_st == action_st and slot_end == action_end:
            free_slots.pop(slot_st)

        elif slot_st == action_st and action_end != slot_st:
            free_slots.insert_after(slot_st, action_end, slot_end)
            free_slots.pop(slot_st)

        elif slot_end == action_end:
            free_slots.updateitem(slot_st, action_st)

        else:
            free_slots.insert_after(slot_st, action_end, slot_end)
            free_slots.updateitem(slot_st, action_st)

        return action_end

    def schedule_lock(
        self,
        new_action: ActionEntity,
        new_action_slot: tuple[str, str],
        entity_id: str,
        lock_queues: Optional[dict[str, Queue[str, ActionInfo]]] = None,
    ) -> None:
        """Scheduled the given action in the lock queue."""
        if not lock_queues:
            lock_queues = self._lineage_table.lock_queues

        new_action_info = ActionInfo(
            new_action.action_id,
            new_action,
            RASC_SCHEDULED,
            LOCK_STATE_SCHEDULED,
            new_action_slot[0],
            new_action_slot[1],
        )

        for action_id, action_info in lock_queues[entity_id].items():
            if not action_info:
                raise ValueError(
                    "Action {}'s schedule information on entity {} is missing.".format(
                        action_id, entity_id
                    )
                )
            if new_action_slot[1] <= action_info.start_time:
                lock_queues[entity_id].insert_before(
                    action_id, new_action.action_id, new_action_info
                )
                _LOGGER.debug(
                    "Schedule the action %s to the lock queue %s",
                    new_action.action_id,
                    entity_id,
                )
                return

        lock_queues[entity_id][new_action.action_id] = new_action_info
        _LOGGER.debug(
            "Schedule action %s to the lock queue %s", new_action.action_id, entity_id
        )

    def same_start_time(self, group_start_time: dict[str, str]) -> bool:
        """Check if all the group commands within an action have the same start time."""
        start_times = list(group_start_time.values())
        return len(set(start_times)) == 1

    def schedule_all_action(
        self,
        action: ActionEntity,
        now: datetime,
        free_slots: dict[str, Queue[str, str]],
        lock_leasing_status: dict[str, str],
    ) -> tuple[bool, datetime]:
        """Schuedle the given action."""

        target_entities = get_target_entities(self._hass, action.action)
        max_end_time = now

        _LOGGER.debug(
            "Start scheduling action %s at time %s",
            action.action_id,
            datetime_to_string(now),
        )

        group_action_start_time: dict[str, str] = {}
        group_slot_start_time: dict[str, str] = {}

        for entity in target_entities:
            entity_id = get_entity_id_from_number(self._hass, entity)

            start_time = self.get_available_ts(
                now, free_slots, entity_id, lock_leasing_status, action
            )

            if not start_time:
                return False, now

            group_action_start_time[entity_id] = max(
                start_time, datetime_to_string(now)
            )
            group_slot_start_time[entity_id] = start_time

        while not self.same_start_time(group_action_start_time):
            next_now = string_to_datetime(
                max(group_action_start_time, key=lambda x: group_action_start_time[x])
            )
            group_action_start_time.clear()
            group_slot_start_time.clear()

            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)

                start_time = self.get_available_ts(
                    next_now, free_slots, entity_id, lock_leasing_status, action
                )
                if not start_time:
                    return False, now

                group_action_start_time[entity_id] = max(
                    start_time, datetime_to_string(next_now)
                )
                group_slot_start_time[entity_id] = start_time

        for entity_id, start_time in group_slot_start_time.items():
            dt_start_time = string_to_datetime(start_time)

            dt_action_st = max(dt_start_time, now)
            dt_action_end = dt_action_st + action.duration[entity_id]
            action_st = datetime_to_string(dt_action_st)
            action_end = datetime_to_string(dt_action_end)

            self.schedule_action(
                (start_time, free_slots[entity_id][start_time]),
                (action_st, action_end),
                free_slots[entity_id],
            )
            self.schedule_lock(action, (action_st, action_end), entity_id)

            max_end_time = max(max_end_time, dt_action_end)

        return True, max_end_time

    def schedule_routine(
        self, hass: HomeAssistant, routine: RoutineEntity
    ) -> tuple[bool, Optional[dict[str, str]]]:
        """Schedule the given routine."""

        _LOGGER.info("Start scheduling the routine %s", routine.routine_id)

        # Remove time slots before now
        self.remove_time_slots_before_now(
            datetime.now(), self._lineage_table.free_slots
        )

        # Deep copy the free slots
        tmp_fs = copy.deepcopy(self._lineage_table.free_slots)

        # Store the current routine lock status
        lock_leasing_status = dict[str, str]()

        # Store the information for the action id
        config: dict[str, Any] = {}
        config[CONF_STEP] = -1
        config[CONF_ROUTINE_ID] = routine.routine_id

        next_end_time: datetime | None = datetime.now()
        for _, script in enumerate(routine.action_script):
            # print("script:", script)
            if not next_end_time:
                return False, None

            if (
                CONF_PARALLEL not in script
                and CONF_SEQUENCE not in script
                and CONF_SERVICE not in script
                and CONF_DELAY not in script
            ):
                config[CONF_STEP] = config[CONF_STEP] + 1
                action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
                action = routine.actions[action_id]

                success, next_end_time = self.schedule_all_action(
                    action, next_end_time, tmp_fs, lock_leasing_status
                )
            else:
                success, next_end_time = self._schedule_routine(
                    hass,
                    script,
                    config,
                    routine,
                    next_end_time,
                    tmp_fs,
                    lock_leasing_status,
                )

            if not success:
                return False, None

        self._lineage_table.free_slots = tmp_fs
        return True, lock_leasing_status

    def _schedule_routine(
        self,
        hass: HomeAssistant,
        script: dict[str, Any],
        config: dict[str, Any],
        routine: RoutineEntity,
        prev_end_time: datetime,
        free_slots: dict[str, Queue],
        lock_leasing_status: dict[str, str],
    ) -> tuple[bool, datetime | None]:
        """Scheudle the given routine with the given script."""
        # print("script:", script)
        next_end_time: datetime | None = prev_end_time

        if CONF_PARALLEL in script:
            item_end_time: datetime | None
            for item in list(script.values())[0]:
                success, item_end_time = self._schedule_routine(
                    hass,
                    item,
                    config,
                    routine,
                    prev_end_time,
                    free_slots,
                    lock_leasing_status,
                )
                if not success or not item_end_time or not next_end_time:
                    return False, None
                next_end_time = max(next_end_time, item_end_time)

        elif CONF_SEQUENCE in script:
            for item in list(script.values())[0]:
                if not next_end_time:
                    return False, None
                success, next_end_time = self._schedule_routine(
                    hass,
                    item,
                    config,
                    routine,
                    next_end_time,
                    free_slots,
                    lock_leasing_status,
                )
                if not success:
                    return False, None

        elif CONF_SERVICE in script:
            service: str = script[CONF_SERVICE]
            domain = service.split(".")[0]
            if domain == DOMAIN_SCRIPT:
                script_component: EntityComponent[BaseScriptEntity] = hass.data[
                    DOMAIN_SCRIPT
                ]

                if not script_component:
                    return False, None

                base_script = script_component.get_entity(list(script.values())[0])
                if base_script and base_script.raw_config:
                    for item in base_script.raw_config[CONF_SEQUENCE]:
                        if not next_end_time:
                            return False, None
                        success, next_end_time = self._schedule_routine(
                            hass,
                            item,
                            config,
                            routine,
                            next_end_time,
                            free_slots,
                            lock_leasing_status,
                        )
                        if not success:
                            return False, None

            else:
                config[CONF_STEP] = config[CONF_STEP] + 1
                action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
                action = routine.actions[action_id]

                if not next_end_time:
                    return False, None
                success, next_end_time = self.schedule_all_action(
                    action, next_end_time, free_slots, lock_leasing_status
                )
                if not success:
                    return False, None

        elif CONF_DELAY in script:
            pass

        else:
            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
            action = routine.actions[action_id]

            if not next_end_time:
                return False, None
            success, next_end_time = self.schedule_all_action(
                action, next_end_time, free_slots, lock_leasing_status
            )

            if not success:
                return False, None

        return True, next_end_time


class FirstComeFirstServeScheduler(BaseScheduler):
    """A class for fcfs scheduler."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
        serialization_order: Queue[str, RoutineInfo],
        scheduling_policy: str,
    ) -> None:
        """Initialize fcfs scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._serialization_order = serialization_order
        self._scheduling_policy = scheduling_policy


class JustInTimeScheduler(BaseScheduler):
    """A class for jit scheduler."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
        serialization_order: Queue[str, RoutineInfo],
        scheduling_policy: str,
    ) -> None:
        """Initialize jit scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._serialization_order = serialization_order
        self._scheduling_policy = scheduling_policy


class TimeLineScheduler(BaseScheduler):
    """A class for timeline scheduler."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
        serialization_order: Queue[str, RoutineInfo],
        scheduling_policy: str,
    ) -> None:
        """Initialize timeline scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._serialization_order = serialization_order
        self._scheduling_policy = scheduling_policy

    def get_next_start_time(
        self, routine: RoutineEntity, new_preset: set[str], postset: set[str]
    ) -> str:
        """Get then next start time for the given routine."""
        # The idea is to reschedule the routine after the routines in the postset.

        target_entities: list[str] = []
        candidates: list[str] = []

        for action in list(routine.actions.values())[:-1]:
            entities = get_target_entities(self._hass, action.action)
            for entity in entities:
                entity_id = get_entity_id_from_number(self._hass, entity)

                if entity_id not in target_entities:
                    target_entities.append(entity_id)

        for routine_id_in_postset in postset:
            routine_in_postset = self._serialization_order[routine_id_in_postset]
            if not routine_in_postset:
                raise ValueError(
                    "The routine {} in the postset is missing from the serialization order".format(
                        routine_id_in_postset
                    )
                )

            for action in list(routine_in_postset.routine.actions.values())[:-1]:
                entities = get_target_entities(self._hass, action.action)
                find_candidate = False
                for entity in entities:
                    entity_id = get_entity_id_from_number(self._hass, entity)

                    if entity_id in target_entities:
                        if entity_id not in self._lineage_table.lock_queues:
                            raise ValueError("Entity %s has no schedule." % entity_id)
                        lock_queue = self._lineage_table.lock_queues[entity_id]
                        if action.action_id not in lock_queue:
                            raise ValueError(
                                "Action {} has not been scheduled on entity {}.".format(
                                    action.action_id, entity_id
                                )
                            )
                        action_info = lock_queue[action.action_id]
                        if not action_info:
                            raise ValueError(
                                "Action {}'s schedule info on entity {} is missing.".format(
                                    action.action_id, entity_id
                                )
                            )
                        candidates.append(action_info.end_time)
                        find_candidate = True

                # Only require to identify the earliest action end time within the existing routines that may cause a serializability conflict.
                if find_candidate:
                    break

        return max(candidates)

    def conflict_determined_serializability_in_case_tl(
        self, preset: set[str], postset: set[str]
    ) -> bool:
        """Check if the determined serializability conflicts."""

        output_all(_LOGGER, serialization_order=self._serialization_order)

        for routine_in_preset in preset:
            idx1 = self._serialization_order.index(routine_in_preset)

            for routine_in_poset in postset:
                idx2 = self._serialization_order.index(routine_in_poset)

                if idx1 > idx2:
                    _LOGGER.error("Conflict determined serializability in timeline")
                    return True

        return False

    def get_available_ts_by_tl(
        self,
        free_slots: dict[str, Queue[str, str]],
        now: datetime,
        entity_id: str,
        lock_leasing_status: dict[str, str],
        preset: set[str],
        postset: set[str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get available time slot by timeline."""
        _LOGGER.debug(
            "Free slots for entity %s: %s",
            entity_id,
            free_slots[entity_id],
        )

        for slot_start, slot_end in free_slots[entity_id].items():
            # Check if the gap is available
            if slot_end and slot_end <= datetime_to_string(now):
                continue

            # Check if the gap is big enough to place the new action
            if (
                slot_end
                and (
                    string_to_datetime(slot_end)
                    - string_to_datetime(max(slot_start, datetime_to_string(now)))
                ).total_seconds()
                < new_action.duration[entity_id].total_seconds()
            ):
                continue

            action_st = max(slot_start, datetime_to_string(now))
            action_end = datetime_to_string(
                string_to_datetime(action_st) + new_action.duration[entity_id]
            )
            cur_preset = preset.union(
                self.get_preset(
                    (action_st, action_end), entity_id, lock_leasing_status, new_action
                )
            )

            cur_postset = postset.union(
                self.get_postset(
                    (action_st, action_end), entity_id, lock_leasing_status, new_action
                )
            )

            if cur_preset.intersection(cur_postset):
                _LOGGER.error(
                    "Attempt to scheduled at the time slot %s with the action start time %s. Intersection conflict",
                    slot_start,
                    action_st,
                )
                continue

            if self.conflict_determined_serializability_in_case_tl(
                cur_preset, cur_postset
            ):
                _LOGGER.error(
                    "Attempt to scheduled at the time slot %s with the action start time %s. Determined serializability conflict",
                    slot_start,
                    action_st,
                )
                continue

            preset.update(cur_preset)
            postset.update(cur_postset)
            return slot_start

        preset.update(cur_preset)
        postset.update(cur_postset)

        return None

    def get_preset(
        self,
        gap: tuple[str, str | None],
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> set[str]:
        """Get preset."""

        gap_start_time = gap[0]
        preset = set[str]()
        for action in self._lineage_table.lock_queues[entity_id].values():
            if not action:
                continue
            if action.end_time <= gap_start_time and get_routine_id(
                action.action_id
            ) != get_routine_id(new_action.action_id):
                preset.add(get_routine_id(action.action_id))
                lock_leasing_status[get_routine_id(action.action_id)] = "post"

        return preset

    def get_postset(
        self,
        gap: tuple[str, str | None],
        entity_id: str,
        lock_leasing_status: dict[str, str],
        new_action: ActionEntity,
    ) -> set[str]:
        """Get postset."""

        gap_end_time = gap[1]
        postset = set[str]()
        if not gap_end_time:
            return postset

        for action in self._lineage_table.lock_queues[entity_id].values():
            if not action:
                continue
            if action.start_time >= gap_end_time and get_routine_id(
                action.action_id
            ) != get_routine_id(new_action.action_id):
                postset.add(get_routine_id(action.action_id))
                lock_leasing_status[get_routine_id(action.action_id)] = "pre"

        return postset

    def get_available_ts_in_case_tl(
        self,
        now: datetime,
        free_slots: dict[str, Queue[str, str]],
        entity_id: str,
        lock_leasing_status: dict[str, str],
        preset: set[str],
        postset: set[str],
        new_action: ActionEntity,
    ) -> str | None:
        """Get the start time of the first available time slot in the entity."""

        start_time = self.get_available_ts_by_tl(
            free_slots, now, entity_id, lock_leasing_status, preset, postset, new_action
        )

        output_all(_LOGGER, preset=preset, postset=postset)

        _LOGGER.debug(
            "The start time of the new time slot for the new action in entity %s is %s",
            entity_id,
            start_time,
        )

        return start_time

    def schedule_all_action_in_case_tl(
        self,
        action: ActionEntity,
        now: datetime,
        free_slots: dict[str, Queue[str, str]],
        lock_leasing_status: dict[str, str],
        preset: set[str],
        postset: set[str],
        lock_queues: dict[str, Queue[str, ActionInfo]] | None = None,
    ) -> tuple[bool, datetime]:
        """Insert action to the free slots at now based on lock leasing approach."""

        target_entities = get_target_entities(self._hass, action.action)
        max_end_time = now

        _LOGGER.debug(
            "Action %s start scheduling at time %s",
            action.action_id,
            datetime_to_string(now),
        )

        group_action_start_time: dict[str, str] = {}
        group_slot_start_time: dict[str, str] = {}

        for entity in target_entities:
            entity_id = get_entity_id_from_number(self._hass, entity)

            start_time = self.get_available_ts_in_case_tl(
                now, free_slots, entity_id, lock_leasing_status, preset, postset, action
            )

            if not start_time:
                _LOGGER.error(
                    "Failed to find a time slot start at %s. Need to reschedule",
                    datetime_to_string(now),
                )
                return False, max_end_time

            group_action_start_time[entity_id] = max(
                start_time, datetime_to_string(now)
            )
            group_slot_start_time[entity_id] = start_time

        while not self.same_start_time(group_action_start_time):
            next_now = string_to_datetime(
                max(group_action_start_time, key=lambda x: group_action_start_time[x])
            )
            group_action_start_time.clear()
            group_slot_start_time.clear()

            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)

                start_time = self.get_available_ts_in_case_tl(
                    next_now,
                    free_slots,
                    entity_id,
                    lock_leasing_status,
                    preset,
                    postset,
                    action,
                )

                if not start_time:
                    _LOGGER.error(
                        "Failed to find a time slot start at %s. Need to reschedule",
                        datetime_to_string(now),
                    )
                    return False, max_end_time

                group_action_start_time[entity_id] = max(
                    start_time, datetime_to_string(next_now)
                )
                group_slot_start_time[entity_id] = start_time

        for entity_id, start_time in group_slot_start_time.items():
            dt_start_time = string_to_datetime(start_time)

            dt_action_st = max(dt_start_time, now)
            dt_action_end = dt_action_st + action.duration[entity_id]
            action_st = datetime_to_string(dt_action_st)
            action_end = datetime_to_string(dt_action_end)

            self.schedule_action(
                (start_time, free_slots[entity_id][start_time]),
                (action_st, action_end),
                free_slots[entity_id],
            )

            self.schedule_lock(action, (action_st, action_end), entity_id, lock_queues)

            max_end_time = max(max_end_time, dt_action_end)

        return True, max_end_time

    def schedule_routine_in_case_tl(
        self, hass: HomeAssistant, routine: RoutineEntity, now: datetime
    ) -> tuple[bool, dict[str, str]]:
        """Schedule the given routine."""

        _LOGGER.info("Start scheduling the routine %s", routine.routine_id)

        # Remove time slots before now
        next_end_time = now
        self.remove_time_slots_before_now(next_end_time, self._lineage_table.free_slots)

        # Deep copy the free slots
        tmp_fs = copy.deepcopy(self._lineage_table.free_slots)

        # Store the current routine lock status
        lock_leasing_status: dict[str, str] = {}

        # Store the information for the action id
        config: dict[str, Any] = {}
        config[CONF_STEP] = -1
        config[CONF_ROUTINE_ID] = routine.routine_id

        preset = set[str]()
        postset = set[str]()

        for _, script in enumerate(routine.action_script):
            # print("script:", script)
            if (
                CONF_PARALLEL not in script
                and CONF_SEQUENCE not in script
                and CONF_SERVICE not in script
                and CONF_DELAY not in script
            ):
                config[CONF_STEP] = config[CONF_STEP] + 1
                action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
                action = routine.actions[action_id]

                success, next_end_time = self.schedule_all_action_in_case_tl(
                    action, next_end_time, tmp_fs, lock_leasing_status, preset, postset
                )
            else:
                success, next_end_time = self._schedule_routine_in_case_tl(
                    hass,
                    script,
                    config,
                    routine,
                    next_end_time,
                    tmp_fs,
                    lock_leasing_status,
                    preset,
                    postset,
                )

            if not success:
                next_start_time = self.get_next_start_time(routine, preset, postset)
                return False, {"next_start_time": next_start_time}

        self._lineage_table.free_slots = tmp_fs
        self.set_earliest_end_time(routine)
        return True, lock_leasing_status

    def _schedule_routine_in_case_tl(
        self,
        hass: HomeAssistant,
        script: dict[str, Any],
        config: dict[str, Any],
        routine: RoutineEntity,
        prev_end_time: datetime,
        free_slots: dict[str, Queue],
        lock_leasing_status: dict[str, str],
        preset: set[str],
        postset: set[str],
    ) -> tuple[bool, datetime]:
        """Schedule the given routine with the given script."""
        # print("script:", script)
        next_end_time = prev_end_time

        if CONF_PARALLEL in script:
            for item in list(script.values())[0]:
                success, item_end_time = self._schedule_routine_in_case_tl(
                    hass,
                    item,
                    config,
                    routine,
                    prev_end_time,
                    free_slots,
                    lock_leasing_status,
                    preset,
                    postset,
                )

                if not success:
                    return False, next_end_time

                next_end_time = max(next_end_time, item_end_time)

        elif CONF_SEQUENCE in script:
            for item in list(script.values())[0]:
                success, next_end_time = self._schedule_routine_in_case_tl(
                    hass,
                    item,
                    config,
                    routine,
                    next_end_time,
                    free_slots,
                    lock_leasing_status,
                    preset,
                    postset,
                )

                if not success:
                    return False, next_end_time

        elif CONF_SERVICE in script:
            temp: str = script[CONF_SERVICE]
            domain = temp.split(".")[0]
            if domain == DOMAIN_SCRIPT:
                script_component: EntityComponent[BaseScriptEntity] = hass.data[
                    DOMAIN_SCRIPT
                ]

                if not script_component:
                    return False, next_end_time

                base_script = script_component.get_entity(list(script.values())[0])
                if base_script and base_script.raw_config:
                    for item in base_script.raw_config[CONF_SEQUENCE]:
                        success, next_end_time = self._schedule_routine_in_case_tl(
                            hass,
                            item,
                            config,
                            routine,
                            next_end_time,
                            free_slots,
                            lock_leasing_status,
                            preset,
                            postset,
                        )

                        if not success:
                            return False, next_end_time

            else:
                config[CONF_STEP] = config[CONF_STEP] + 1
                action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
                action = routine.actions[action_id]

                success, next_end_time = self.schedule_all_action_in_case_tl(
                    action,
                    next_end_time,
                    free_slots,
                    lock_leasing_status,
                    preset,
                    postset,
                )
                if not success:
                    return False, next_end_time

        elif CONF_DELAY in script:
            pass

        else:
            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
            action = routine.actions[action_id]

            success, next_end_time = self.schedule_all_action_in_case_tl(
                action, next_end_time, free_slots, lock_leasing_status, preset, postset
            )

            if not success:
                return False, next_end_time

        return True, next_end_time

    def set_earliest_end_time(self, routine: RoutineEntity) -> None:
        """Set the earliest end time of the given routine for rescheduling."""
        min_end_time: None | str = None
        min_end_time_entity_id: str

        for action in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                if entity_id not in self._lineage_table.lock_queues:
                    raise ValueError("Entity %s has no schedule." % entity_id)
                if action.action_id not in self._lineage_table.lock_queues[entity_id]:
                    raise ValueError(
                        "Action {} has not been scheduled on entity {}.".format(
                            action.action_id, entity_id
                        )
                    )
                action_info = self._lineage_table.lock_queues[entity_id][
                    action.action_id
                ]
                if not action_info:
                    raise ValueError(
                        "Action {}'s schedule information on entity {} is missing.".format(
                            action.action_id, entity_id
                        )
                    )
                if not min_end_time:
                    min_end_time_entity_id = entity_id
                    min_end_time = action_info.end_time
                elif (
                    entity_id == min_end_time_entity_id
                    and action_info.end_time > min_end_time
                ):
                    min_end_time = action_info.end_time
                elif (
                    entity_id != min_end_time_entity_id
                    and action_info.end_time < min_end_time
                ):
                    min_end_time_entity_id = entity_id
                    min_end_time = action_info.end_time

        if not min_end_time:
            return

        routine.earliest_end_time = min_end_time


class RascalScheduler(BaseScheduler):
    """A class for rascal scheduler."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize rascal scheduler."""
        self._hass = hass
        self._lineage_table = LineageTable()
        self._serialization_order = Queue[str, RoutineInfo]()
        self._lock_waitlist = dict[str, list[str]]()
        self._wait_queue = Queue[str, WaitRoutineInfo]()
        self._hass.bus.async_listen(RASC_RESPONSE, self.handle_event)
        self._scheduling_policy: str = config[SCHEDULING_POLICY]
        self._scheduler: BaseScheduler | TimeLineScheduler | None = (
            self._get_scheduler()
        )
        self._logging: bool = True
        self._reschedule_handler: Optional[
            Callable[[Event], Coroutine[Any, Any, None]]
        ] = None
        self._metrics = ScheduleMetrics(self._scheduling_policy)

    @property
    def lineage_table(self) -> LineageTable:
        """Get lineage table."""
        return self._lineage_table

    @lineage_table.setter
    def lineage_table(self, lt: LineageTable) -> None:
        """Set lineage table."""
        self._lineage_table = lt

    @property
    def serialization_order(self) -> Queue[str, RoutineInfo]:
        """Get serialization order."""
        return self._serialization_order

    @property
    def wait_queue(self) -> Queue[str, WaitRoutineInfo]:
        """Get wait queue."""
        return self._wait_queue

    def add_entity(self, entity_id: str) -> None:
        """Add lock waitlist."""
        self._lock_waitlist[entity_id] = []

    def delete_entity(self, entity_id: str) -> None:
        """Delete lock waitlist."""
        del self._lock_waitlist[entity_id]

    def duplicate_locks(self) -> dict[str, str | None]:
        """Duplicate locks."""
        return copy.deepcopy(self._lineage_table.locks)

    def duplicate_lock_queues(self) -> dict[str, Queue[str, ActionInfo]]:
        """Duplicate lock queues."""
        lock_queues = dict[str, Queue[str, ActionInfo]]()
        for entity_id, queue in self._lineage_table.lock_queues.items():
            for action_id, action_info in queue.items():
                if entity_id not in lock_queues:
                    lock_queues[entity_id] = Queue[str, ActionInfo]()
                if not action_info:
                    raise ValueError(
                        "Action {}'s schedule information on entity {} is missing.".format(
                            action_id, entity_id
                        )
                    )
                lock_queues[entity_id][action_id] = ActionInfo(
                    action_id=action_info.action_id,
                    action=action_info.action,
                    action_state=action_info.action_state,
                    lock_state=action_info.lock_state,
                    start_time=action_info.start_time,
                    end_time=action_info.end_time,
                )
        return lock_queues

    @property
    def metrics(self) -> ScheduleMetrics:
        """Get schedule metrics."""
        return self._metrics

    def _get_scheduler(self) -> BaseScheduler | TimeLineScheduler | None:
        """Get scheduler."""

        if self._scheduling_policy in (FCFS, FCFS_POST):
            return FirstComeFirstServeScheduler(
                self._hass,
                self._lineage_table,
                self._serialization_order,
                self._scheduling_policy,
            )

        if self._scheduling_policy in (JIT):
            return JustInTimeScheduler(
                self._hass,
                self._lineage_table,
                self._serialization_order,
                self._scheduling_policy,
            )

        if self._scheduling_policy in (TIMELINE):
            return TimeLineScheduler(
                self._hass,
                self._lineage_table,
                self._serialization_order,
                self._scheduling_policy,
            )

        return None

    @property
    def reschedule_handler(self) -> Callable[[Event], Coroutine[Any, Any, None]] | None:
        """Return the reschedule handler function.

        The reschedule handler function is responsible for handling events for the rescheduler.

        Returns:
            Callable[[Event], Coroutine[Any, Any, None]]: The reschedule handler function.
        """
        return self._reschedule_handler

    @reschedule_handler.setter
    def reschedule_handler(
        self, handler: Callable[[Event], Coroutine[Any, Any, None]]
    ) -> None:
        """Set the handler function for the scheduler.

        Args:
            handler (Callable[[Event], Coroutine[Any, Any, None]]): The handler function of the rescheduled.
        """
        if not self._reschedule_handler:
            self._reschedule_handler = handler

    def _add_routine_to_serialization_order(
        self, routine: RoutineEntity, lock_leasing_status: dict[str, str]
    ) -> None:
        """Add routine to the serialization order."""
        routine_info = RoutineInfo(routine.routine_id, routine)
        self._serialization_order[routine.routine_id] = routine_info

        # Move the routine forward if prelease
        filtered_status = {
            key: value for key, value in lock_leasing_status.items() if value == "pre"
        }

        idx1 = self._serialization_order.index(routine.routine_id)
        for key in filtered_status:
            idx2 = self._serialization_order.index(key)

            if idx1 > idx2:
                self._remove_routine_from_serialization_order(routine.routine_id)
                self._serialization_order.insert_before(
                    key, routine.routine_id, routine_info
                )

        _LOGGER.debug("Add routine %s to the serialization order", routine.routine_id)
        output_all(_LOGGER, serialization_order=self._serialization_order)

    def _remove_routine_from_serialization_order(self, routine_id: str) -> None:
        """Remove routine from the serialization order."""
        _LOGGER.info("Remove routine %s from the serialization order", routine_id)
        self._serialization_order.pop(routine_id)

    def _remove_routine_from_lock_queues(self, routine: RoutineEntity) -> None:
        """Remove routine from lock queues."""
        for action in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                if action.action_id is not None:
                    self._lineage_table.lock_queues[entity_id].pop(action.action_id)

    def _add_routine_to_wait_queues(self, routine: RoutineEntity) -> None:
        """Add routine to the wait queue."""
        if not routine.routine_id:
            raise ValueError("Routine id is not found")
        for action in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                if routine.routine_id not in self._lock_waitlist[entity_id]:
                    self._lock_waitlist[entity_id].append(routine.routine_id)

        self._wait_queue[routine.routine_id] = WaitRoutineInfo(
            routine.routine_id, routine
        )

        _LOGGER.info("Add routine %s to the wait queue", routine.routine_id)
        output_all(
            _LOGGER, lock_waitlist=self._lock_waitlist, wait_queue=self._wait_queue
        )

    def _remove_routine_from_wait_queue(self, routine_id: str) -> None:
        """Remove routine from the wait queue."""
        routine_info = self._wait_queue.pop(routine_id)
        if not routine_info:
            raise ValueError("Routine %s is not found in the wait queue" % routine_id)
        routine = routine_info.routine

        for action in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                while routine_id in self._lock_waitlist[entity_id]:
                    self._lock_waitlist[entity_id].remove(routine_id)

        _LOGGER.info("Remove routine %s from the wait queue", routine_id)

    def _acquire_routine_locks(self, routine: RoutineEntity) -> bool:
        """Acquire all locks for the routine."""

        locks = self.duplicate_locks()
        lock_queues = self.duplicate_lock_queues()

        for action in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                if not self._attempt_lock(
                    action.action_id, entity_id, locks, lock_queues
                ):
                    _LOGGER.error(
                        "Routine %s failed to acquired all the locks",
                        routine.routine_id,
                    )
                    return False

        _LOGGER.info("Routine %s acquired all the locks", routine.routine_id)
        output_all(
            _LOGGER,
            locks=self._lineage_table.locks,
            lock_queues=self._lineage_table.lock_queues,
            serialization_order=self._serialization_order,
        )

        for entity_id, routine_id in locks.items():
            self._lineage_table.locks[entity_id] = routine_id

        for entity_id, lock_queue in lock_queues.items():
            self._lineage_table.lock_queues[entity_id] = lock_queue

        return True

    def _attempt_lock(
        self,
        action_id: str,
        entity_id: str,
        locks: dict[str, str | None],
        lock_queues: dict[str, Queue[str, ActionInfo]],
    ) -> bool:
        """Attempt the lock for the given action."""
        if entity_id not in lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )

        # if there is no routine accessing the lock
        if not locks[entity_id]:
            locks[entity_id] = get_routine_id(action_id)
            action_lock.lock_state = LOCK_STATE_ACQUIRED
            return True

        # if the routine already access the lock
        if locks[entity_id] == get_routine_id(action_id):
            action_lock.lock_state = LOCK_STATE_ACQUIRED
            return True

        # if another routine is accessing the lock
        # check if the action can acquire the lock through prelease
        action_with_lock = self.get_first_action_with_acquired_lock(entity_id)
        if action_with_lock and get_routine_id(
            action_with_lock.action_id
        ) != get_routine_id(action_id):
            old_idx = lock_queues[entity_id].index(action_with_lock.action_id)
            new_idx = lock_queues[entity_id].index(action_id)

            prev_action_with_lock = lock_queues[entity_id].prev(
                action_with_lock.action_id
            )

            if (
                new_idx < old_idx
                and prev_action_with_lock
                and get_routine_id(prev_action_with_lock.action_id)
                == get_routine_id(action_id)
                and action_with_lock.action_state
                not in (RASC_ACK, RASC_START, RASC_COMPLETE)
            ):
                self._prelease_lock(action_with_lock.action_id, entity_id, lock_queues)
                locks[entity_id] = get_routine_id(action_id)

                action_lock.lock_state = LOCK_STATE_ACQUIRED
                return True

        # if another routine is accessing the lock
        # check if the action can acquire the lock through postlease
        action_with_lock = self.get_last_action_with_acquired_lock(entity_id)
        if action_with_lock and get_routine_id(
            action_with_lock.action_id
        ) != get_routine_id(action_id):
            old_idx = lock_queues[entity_id].index(action_with_lock.action_id)
            new_idx = lock_queues[entity_id].index(action_id)

            next_action_with_lock = lock_queues[entity_id].next(
                action_with_lock.action_id
            )

            if self._scheduling_policy in (FCFS, FCFS_POST, JIT):
                if (
                    new_idx > old_idx
                    and next_action_with_lock
                    and get_routine_id(next_action_with_lock.action_id)
                    == get_routine_id(action_id)
                    and action_with_lock.action_state in (RASC_START, RASC_COMPLETE)
                ):
                    self._postlease_lock(
                        action_with_lock.action_id, entity_id, lock_queues
                    )
                    locks[entity_id] = get_routine_id(action_id)
                    action_lock.lock_state = LOCK_STATE_ACQUIRED
                    return True

            elif (
                new_idx > old_idx
                and next_action_with_lock
                and get_routine_id(next_action_with_lock.action_id)
                == get_routine_id(action_id)
                # and action_with_lock.action_state in (RASC_START, RASC_COMPLETE)
            ):
                self._postlease_lock(action_with_lock.action_id, entity_id, lock_queues)
                locks[entity_id] = get_routine_id(action_id)
                action_lock.lock_state = LOCK_STATE_ACQUIRED
                return True

        _LOGGER.error("Action %s failed to acquired the lock %s", action_id, entity_id)
        return False

    def _acquire_lock(self, action_id: str, entity_id: str) -> None:
        """Acquire the lock for the given action in the lock queue."""
        self._lineage_table.locks[entity_id] = get_routine_id(action_id)
        self._update_action_lock_state(action_id, entity_id, LOCK_STATE_ACQUIRED)

    def _prelease_lock(
        self,
        action_id: str,
        entity_id: str,
        lock_queues: dict[str, Queue[str, ActionInfo]],
    ) -> None:
        """Prelease the lock from the given action."""

        routine_id = get_routine_id(action_id)

        if entity_id not in lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action_lock.lock_state = LOCK_STATE_LEASED

        next_action = lock_queues[entity_id].next(action_id)
        while next_action and get_routine_id(next_action.action_id) == routine_id:
            next_action.lock_state = LOCK_STATE_LEASED
            next_action = lock_queues[entity_id].next(next_action.action_id)

    def _postlease_lock(
        self,
        action_id: str,
        entity_id: str,
        lock_queues: dict[str, Queue[str, ActionInfo]],
    ) -> None:
        """Postlease the lock from the given action."""

        routine_id = get_routine_id(action_id)

        if entity_id not in lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action_lock = lock_queues[entity_id][action_id]
        if not action_lock:
            raise ValueError(
                "Action {}'s schedule information on entity {} is missing.".format(
                    action_id, entity_id
                )
            )
        action_lock.lock_state = LOCK_STATE_RELEASED

        prev_action = lock_queues[entity_id].prev(action_id)
        while prev_action and get_routine_id(prev_action.action_id) == routine_id:
            prev_action.lock_state = LOCK_STATE_RELEASED
            prev_action = lock_queues[entity_id].prev(prev_action.action_id)

    def _release_routine_locks(self, routine: RoutineEntity) -> None:
        """Release all the locks for the given routine."""
        for action in list(routine.actions.values())[:-1]:
            self._release_all_locks(action)

        _LOGGER.info("Release all locks for the routine %s", routine.routine_id)

    def _release_all_locks(self, action: ActionEntity) -> None:
        """Release all locks for the given action."""
        target_entities = get_target_entities(self._hass, action.action)
        for entity in target_entities:
            entity_id = get_entity_id_from_number(self._hass, entity)
            if self._lineage_table.locks[entity_id] == get_routine_id(action.action_id):
                self._release_lock(entity_id)

    def _release_lock(self, entity_id: str) -> None:
        """Release the lock for the given entity."""
        self._lineage_table.locks[entity_id] = None

    def _get_first_action_with_acquired_lock(self, entity_id: str) -> ActionInfo | None:
        """Get the first action with acquired_lock."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        lock_queue = self._lineage_table.lock_queues[entity_id]
        return next(
            (
                action_info
                for action_info in lock_queue.values()
                if action_info and action_info.lock_state == LOCK_STATE_ACQUIRED
            ),
            None,
        )

    def _get_last_action_with_acquired_lock(self, entity_id: str) -> ActionInfo | None:
        """Get the last action with acquired_lock."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        lock_queue = self._lineage_table.lock_queues[entity_id]
        return next(
            (
                action_info
                for action_info in reversed(list(lock_queue.values()))
                if action_info and action_info.lock_state == LOCK_STATE_ACQUIRED
            ),
            None,
        )

    def _remove_scheduled_actions(self, routine_id: str) -> None:
        """Remove all scheduled actions of the given routine in the lock queues."""
        for lock_queue in self._lineage_table.lock_queues.values():
            for action_id, action_info in lock_queue.items():
                if (
                    action_info is not None
                    and action_info.lock_state == LOCK_STATE_SCHEDULED
                    and routine_id == get_routine_id(action_id)
                ):
                    lock_queue.pop(action_id)

        _LOGGER.debug("Remove all scheduled actions of the routine %s", routine_id)

    def _eligibility_test(self, routine: RoutineEntity) -> bool:
        """Eligibility test for the routine."""

        _LOGGER.info("Start eligibility test for the routine %s", routine.routine_id)

        if not self._scheduler:
            return False

        if self._scheduling_policy in (FCFS, FCFS_POST, JIT):
            if isinstance(self._scheduler, TimeLineScheduler):
                raise TypeError("The scheduler should not be TimeLineScheduler")
            success, lock_leasing_status = self._scheduler.schedule_routine(
                self._hass, routine
            )

            if success:
                if not lock_leasing_status:
                    raise ValueError(
                        "Failed to schedule the routine {}. There should be a lock leasing status.".format(
                            routine.routine_id
                        )
                    )
                self._add_routine_to_serialization_order(routine, lock_leasing_status)
                self._acquire_routine_locks(routine)
                routine_info = self._serialization_order[routine.routine_id]
                if not routine_info:
                    raise ValueError(
                        "Routine %s is not found in the serialization order"
                        % routine.routine_id
                    )
                routine_info.pass_eligibility = True
                _LOGGER.info("Routine %s pass the eligibility test", routine.routine_id)
                return True

            self._remove_scheduled_actions(routine.routine_id)
            _LOGGER.error(
                "Routine %s failed to pass the eligibility test", routine.routine_id
            )
            return False

        # timeline scheduler
        if not isinstance(self._scheduler, TimeLineScheduler):
            raise TypeError(
                "The scheduler should be TimeLineScheduler for the timeline scheduling policy"
            )
        success, lock_leasing_status = self._scheduler.schedule_routine_in_case_tl(
            self._hass, routine, datetime.now()
        )
        while not success:
            if (
                not lock_leasing_status
                or "next_start_time" not in lock_leasing_status
                or not lock_leasing_status["next_start_time"]
            ):
                raise ValueError(
                    "Failed to reschedule the routine {}. There should be a next start time for rescheduling".format(
                        routine.routine_id
                    )
                )

            self._remove_scheduled_actions(routine.routine_id)
            # rescheule the routine
            success, lock_leasing_status = self._scheduler.schedule_routine_in_case_tl(
                self._hass,
                routine,
                string_to_datetime(lock_leasing_status["next_start_time"]),
            )

        self._add_routine_to_serialization_order(routine, lock_leasing_status)
        if self._acquire_routine_locks(routine):
            routine_info = self._serialization_order[routine.routine_id]
            if not routine_info:
                raise ValueError(
                    "Routine %s is not found in the serialization order"
                    % routine.routine_id
                )
            routine_info.pass_eligibility = True
            _LOGGER.info("Routine %s pass the eligibility test", routine.routine_id)

            output_all(
                _LOGGER,
                locks=self._lineage_table.locks,
                lock_queues=self._lineage_table.lock_queues,
                free_slots=self._lineage_table.free_slots,
                serialization_order=self._serialization_order,
            )

            return True

        _LOGGER.error(
            "Routine %s failed to pass the eligibility test", routine.routine_id
        )
        return False

    def initialize_routine(self, routine: RoutineEntity) -> None:
        """Initialize the given routine."""
        _LOGGER.info("New coming routine %s", routine.routine_id)
        action_ids = set(routine.actions.keys())
        self._metrics.record_routine_arrival(
            routine.routine_id, datetime.now(), action_ids
        )

        if self._eligibility_test(routine):
            output_all(
                _LOGGER,
                locks=self._lineage_table.locks,
                lock_queues=self._lineage_table.lock_queues,
                free_slots=self._lineage_table.free_slots,
                serialization_order=self._serialization_order,
            )

            self._start_routine(routine)
        elif self._scheduling_policy not in (TIMELINE):
            self._add_routine_to_wait_queues(routine)

    def _start_routine(self, routine: RoutineEntity) -> None:
        """Start the given routine."""

        _LOGGER.info("Start the routine %s", routine.routine_id)

        # Start the action that doesn't have the parents
        for action_entity in list(routine.actions.values())[:-1]:
            if not action_entity.parents:
                self._start_action(action_entity)

    def _start_action(self, action: ActionEntity) -> None:
        """Start the given action."""

        if self._is_action_ready(action):
            _LOGGER.info("Start the action %s", action.action_id)
            self._hass.async_create_task(action.attach_triggered(log_exceptions=False))

    def _is_action_ready(self, action: ActionEntity) -> bool:
        """Check if the given action acquire all the associated locks to get executed."""

        _LOGGER.debug("Check if action %s is ready", action.action_id)
        output_all(
            _LOGGER,
            locks=self._lineage_table.locks,
            lock_queues=self._lineage_table.lock_queues,
        )

        if self._scheduling_policy in (FCFS, FCFS_POST, JIT):
            # Check if the action acquires all the locks
            target_entities = get_target_entities(self._hass, action.action)
            if any(
                self._lineage_table.locks[get_entity_id_from_number(self._hass, entity)]
                != get_routine_id(action.action_id)
                for entity in target_entities
            ):
                _LOGGER.error(
                    "Failed to get all the locks for the action %s",
                    action.action_id,
                )
                return False

            # Check if the action reach the start time
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)

                lock_queues = self._lineage_table.lock_queues
                if entity_id not in lock_queues:
                    raise ValueError("Entity %s has no schedule." % entity_id)
                if action.action_id not in lock_queues[entity_id]:
                    raise ValueError(
                        f"Action {action.action_id} has not been scheduled on entity {entity_id}."
                    )
                action_lock = lock_queues[entity_id][action.action_id]
                if not action_lock:
                    raise ValueError(
                        "Action {}'s schedule information on entity {} is missing.".format(
                            action.action_id, entity_id
                        )
                    )

                if action_lock.start_time > datetime_to_string(datetime.now()):
                    _LOGGER.error(
                        "Action %s hasn't reach the start time %s",
                        action.action_id,
                        action_lock.start_time,
                    )
                    return False

            return True

        # timeline scheduler
        routine_info = self._serialization_order[get_routine_id(action.action_id)]
        if not routine_info:
            raise ValueError(
                "Routine %s is not found in the serialization order"
                % get_routine_id(action.action_id)
            )
        if not routine_info.pass_eligibility:
            return False

        # Check if the action reach the start time
        target_entities = get_target_entities(self._hass, action.action)
        for entity in target_entities:
            entity_id = get_entity_id_from_number(self._hass, entity)

            lock_queues = self._lineage_table.lock_queues
            if entity_id not in lock_queues:
                raise ValueError("Entity %s has no schedule." % entity_id)
            if action.action_id not in lock_queues[entity_id]:
                _LOGGER.debug(
                    "entity %s's lock queue: %s", entity_id, lock_queues[entity_id]
                )
                raise ValueError(
                    f"Action {action.action_id} has not been scheduled on entity {entity_id}."
                )
            action_lock = lock_queues[entity_id][action.action_id]
            if not action_lock:
                raise ValueError(
                    "Action {}'s schedule information on entity {} is missing.".format(
                        action.action_id, entity_id
                    )
                )
            if action_lock.start_time > datetime_to_string(datetime.now()):
                _LOGGER.error(
                    "Action %s hasn't reach the start time %s",
                    action.action_id,
                    action_lock.start_time,
                )
                return False

        return True

    async def handle_event(self, event: Event) -> None:  # noqa: C901
        """Handle event."""
        _LOGGER.debug("Handling event %s on the scheduler", event)
        if self._reschedule_handler is not None:
            await self._reschedule_handler(event)

        event_type: Optional[str] = event.data.get(CONF_TYPE)
        entity_id: Optional[str] = event.data.get(CONF_ENTITY_ID)
        action_id: Optional[str] = event.data.get(ATTR_ACTION_ID)

        # Skip the event if the action is manually executed
        if (
            not self._serialization_order
            or not entity_id
            or not action_id
            or not event_type
        ):
            return

        # update the action state
        self._update_action_state(action_id, entity_id, event_type)

        # Get the running action in the serialization
        action = self.get_action(action_id)
        if not action:
            return

        if event_type == RASC_ACK:
            # Check if the action is acknowledged
            if self._is_all_actions_ack(action):
                _LOGGER.info("Group action %s is acked", action_id)

                self._set_action_acked(action_id)

        elif event_type == RASC_START:
            self._metrics.record_action_start(event.time_fired, entity_id, action_id)
            # Check if the action has started
            if self._is_all_actions_start(action):
                _LOGGER.info("Group action %s is started", action_id)

                self._set_action_started(action_id)

        elif event_type == RASC_COMPLETE:
            # Delay the action
            if action.delay:
                await action.async_delay_step()

            # Emulate action's duration
            await self._async_wait_until(action_id, entity_id)

            self._metrics.record_action_end(event.time_fired, entity_id, action_id)

            _LOGGER.info("Action %s on entity %s is completed", action_id, entity_id)

            output_all(_LOGGER, lock_queues=self._lineage_table.lock_queues)

            if self._scheduling_policy == FCFS_POST:
                self._start_ready_routines_fcfs_post(entity_id)

            elif self._scheduling_policy == JIT:
                if not self._return_lock(action_id, entity_id):
                    self._start_ready_routines_jit(entity_id)

            elif self._scheduling_policy == TIMELINE:
                if not self._return_lock(action_id, entity_id):
                    self._start_ready_routines_tl(action_id, entity_id)

            # Check if the action is completed
            if self._is_all_actions_complete(action):
                _LOGGER.info("All commands in the action %s is completed", action_id)

                self._set_action_completed(action_id)

                self._run_next_action(action)

        else:
            output_all(_LOGGER, lock_queues=self._lineage_table.lock_queues)

    def _return_lock(self, action_id: str, entity_id: str) -> bool:
        """Check if the given action returns the lock."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )

        next_action = self._lineage_table.lock_queues[entity_id].next(action_id)
        if not next_action:
            return False

        if get_routine_id(next_action.action_id) == get_routine_id(action_id):
            return False

        if next_action.lock_state != LOCK_STATE_LEASED:
            return False

        self._postlease_lock(action_id, entity_id, self._lineage_table.lock_queues)
        self._acquire_lock(next_action.action_id, entity_id)

        cur_action = next_action
        next_action = self._lineage_table.lock_queues[entity_id].next(
            next_action.action_id
        )
        while next_action and get_routine_id(cur_action.action_id) == get_routine_id(
            next_action.action_id
        ):
            self._acquire_lock(next_action.action_id, entity_id)
            next_action = self._lineage_table.lock_queues[entity_id].next(
                next_action.action_id
            )
            if not next_action:
                break
            _LOGGER.debug(
                "Action %s returns the lock %s to the action %s",
                action_id,
                entity_id,
                next_action.action_id,
            )

        output_all(
            _LOGGER,
            locks=self._lineage_table.locks,
            lock_queues=self._lineage_table.lock_queues,
        )

        if self._condition_check(cur_action.action):
            self._start_action(cur_action.action)

        return True

    def _set_action_acked(self, action_id: str) -> None:
        """Set the action of the entity acked."""
        routine_info = self._serialization_order.get(get_routine_id(action_id))
        if not routine_info:
            raise ValueError(
                "Routine %s is not in the serialization order."
                % get_routine_id(action_id)
            )
        action = routine_info.routine.actions[action_id]
        if not action:
            raise ValueError("Action %s is not in the routine script." % action_id)
        action.action_acked = True

    def _set_action_started(self, action_id: str) -> None:
        """Set the action of the entity started."""
        routine_info = self._serialization_order.get(get_routine_id(action_id))
        if not routine_info:
            raise ValueError(
                "Routine %s is not in the serialization order."
                % get_routine_id(action_id)
            )
        action = routine_info.routine.actions[action_id]
        if not action:
            raise ValueError("Action %s is not in the routine script." % action_id)
        action.action_started = True

    def _set_action_completed(self, action_id: str) -> None:
        """Set the action of the entity completed."""
        _LOGGER.debug("Set the action %s to completed", action_id)
        routine_info = self._serialization_order[get_routine_id(action_id)]
        if not routine_info:
            raise ValueError(
                "Routine %s is not in the serialization order."
                % get_routine_id(action_id)
            )
        action = routine_info.routine.actions[action_id]
        if not action:
            raise ValueError("Action %s is not in the routine script." % action_id)
        action.action_completed = True

    def _update_action_lock_state(
        self, action_id: str, entity_id: str, state: str
    ) -> None:
        """Update action lock state."""
        _LOGGER.debug(
            "Update action %s lock state in entity %s to %s",
            action_id,
            entity_id,
            state,
        )
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action = self._lineage_table.lock_queues[entity_id].get(action_id)
        if action:
            action.lock_state = state

    def _update_action_state(
        self, action_id: str, entity_id: str, new_state: str
    ) -> None:
        """Update the action state."""
        _LOGGER.debug(
            "Update action %s's running state in entity %s to state %s",
            action_id,
            entity_id,
            new_state,
        )
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action = self._lineage_table.lock_queues[entity_id].get(action_id)
        if action:
            action.action_state = new_state

    async def _async_wait_until(self, action_id: str, entity_id: str) -> None:
        """Wait until the time reaches the end time of the action."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )
        action = self._lineage_table.lock_queues[entity_id].get(action_id)
        if not action:
            return
        action_end = action.end_time
        wait_seconds = (string_to_datetime(action_end) - datetime.now()).total_seconds()

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    def _is_action_state(self, action: ActionEntity, entity: str, state: str) -> bool:
        """Check if the action is completed."""
        if action.action_id is None:
            return False
        lock = self._lineage_table.lock_queues[
            get_entity_id_from_number(self._hass, entity)
        ][action.action_id]
        if lock is not None:
            if lock.action_state != state:
                return False
        return True

    def is_action_ack(self, action: ActionEntity, entity: str) -> bool:
        """Check if the action is acked."""
        return self._is_action_state(action, entity, RASC_ACK)

    def is_action_start(self, action: ActionEntity, entity: str) -> bool:
        """Check if the action has started."""
        return self._is_action_state(action, entity, RASC_START)

    def is_action_complete(self, action: ActionEntity, entity: str) -> bool:
        """Check if the action is completed."""
        return self._is_action_state(action, entity, RASC_START)

    def _is_all_actions_state(self, action: ActionEntity, state: str) -> bool:
        """Check if the action is at the requested state on all affected entities."""
        if action.action_id is None:
            return False
        for entity in get_target_entities(self._hass, action.action):
            lock = self._lineage_table.lock_queues[
                get_entity_id_from_number(self._hass, entity)
            ][action.action_id]
            if lock:
                if lock.action_state != state:
                    return False
        return True

    def _is_all_actions_ack(self, action: ActionEntity) -> bool:
        return self._is_all_actions_state(action, RASC_ACK)

    def _is_all_actions_start(self, action: ActionEntity) -> bool:
        return self._is_all_actions_state(action, RASC_START)

    def _is_all_actions_complete(self, action: ActionEntity) -> bool:
        return self._is_all_actions_state(action, RASC_COMPLETE)

    # continue to do, need to check condition variable
    def _condition_check(self, action: ActionEntity) -> bool:
        """Condition check."""
        return all(parent.action_completed for parent in action.parents)

    def _run_next_action(self, action: ActionEntity) -> None:
        """Run the entity's next action."""

        # This is not the end of the routine
        for child in action.children:
            if self._condition_check(child):
                if not child.is_end_node:
                    self._start_action(child)
                else:
                    _LOGGER.info(
                        "This is the end of the routine %s",
                        get_routine_id(action.action_id),
                    )
                    self._handle_end_of_routine(get_routine_id(action.action_id))

    def _handle_end_of_routine(self, routine_id: str) -> None:
        """Handle the end of the routine."""

        routine_info = self._serialization_order[routine_id]
        if not routine_info:
            raise ValueError("Routine %s is not found in the serialization order")
        routine = routine_info.routine

        self._remove_routine_from_lock_queues(routine)
        self._release_routine_locks(routine)
        self._remove_routine_from_serialization_order(routine_id)

        if self._scheduling_policy == FCFS:
            self._start_ready_routines_fcfs()

    def _start_ready_routines_fcfs(self) -> None:
        """Start the ready routine by fcfs."""
        ready_routines: list[str] = []
        for routine_id in self._wait_queue:
            routine_info = self._wait_queue[routine_id]
            if not routine_info:
                raise ValueError(
                    "Routine %s is not found in the wait queue" % routine_id
                )
            routine = routine_info.routine
            if self._eligibility_test(routine):
                output_all(
                    _LOGGER,
                    locks=self._lineage_table.locks,
                    lock_queues=self._lineage_table.lock_queues,
                    free_slots=self._lineage_table.free_slots,
                    serialization_order=self._serialization_order,
                )
                ready_routines.append(routine_id)

        for routine_id in ready_routines:
            routine_info = self._wait_queue[routine_id]
            if not routine_info:
                raise ValueError(
                    "Routine %s is not found in the wait queue" % routine_id
                )
            routine = routine_info.routine
            self._remove_routine_from_wait_queue(routine_id)
            self._start_routine(routine)

    def _start_ready_routines_fcfs_post(self, entity_id: str) -> None:
        """Start the ready routine by fcfs_post."""
        if entity_id in self._lock_waitlist and self._lock_waitlist[entity_id]:
            next_routine_info = self._wait_queue[self._lock_waitlist[entity_id][0]]
            if not next_routine_info:
                raise ValueError(
                    "Routine %s is not found in the wait queue"
                    % self._lock_waitlist[entity_id][0]
                )
            next_routine = next_routine_info.routine

            if self._eligibility_test(next_routine):
                _LOGGER.info(
                    "Routine %s passes the eligibility test", next_routine.routine_id
                )
                output_all(
                    _LOGGER,
                    locks=self._lineage_table.locks,
                    lock_queues=self._lineage_table.lock_queues,
                    free_slots=self._lineage_table.free_slots,
                    serialization_order=self._serialization_order,
                )

                self._remove_routine_from_wait_queue(next_routine.routine_id)
                self._start_routine(next_routine)

    def _start_ready_routines_jit(self, entity_id: str) -> None:
        """Start the ready routine by jit."""

        for next_routine_id in self._lock_waitlist[entity_id]:
            next_routine_info = self._wait_queue[next_routine_id]
            if not next_routine_info:
                raise ValueError(
                    "Routine %s is not found in the wait queue" % next_routine_id
                )
            next_routine = next_routine_info.routine

            if self._eligibility_test(next_routine):
                _LOGGER.info("Routine %s passes the eligibility test", next_routine_id)
                output_all(
                    _LOGGER,
                    locks=self._lineage_table.locks,
                    lock_queues=self._lineage_table.lock_queues,
                    free_slots=self._lineage_table.free_slots,
                    serialization_order=self._serialization_order,
                )

                self._remove_routine_from_wait_queue(next_routine_id)
                self._start_routine(next_routine)
                return

            if next_routine_info.ttl > 0:
                next_routine_info.ttl -= 1
            else:
                return

    def _start_ready_routines_tl(self, action_id: str, entity_id: str) -> None:
        """Test and start the ready routine."""
        if entity_id not in self._lineage_table.lock_queues:
            raise ValueError("Entity %s has no schedule." % entity_id)
        if action_id not in self._lineage_table.lock_queues[entity_id]:
            raise ValueError(
                f"Action {action_id} has not been scheduled on entity {entity_id}."
            )

        next_action = self._lineage_table.lock_queues[entity_id].next(action_id)

        if not next_action:
            return

        next_routine = self._serialization_order[get_routine_id(next_action.action_id)]

        if not next_routine:
            raise ValueError(
                "Routine %s is not found in the serialization order"
                % get_routine_id(next_action.action_id)
            )

        if not next_routine.pass_eligibility and self._acquire_routine_locks(
            next_routine.routine
        ):
            _LOGGER.info(
                "Routine %s passes the eligibility test", next_routine.routine_id
            )
            next_routine.pass_eligibility = True
            self._start_routine(next_routine.routine)

        if next_routine.pass_eligibility and self._condition_check(next_action.action):
            self._start_action(next_action.action)
