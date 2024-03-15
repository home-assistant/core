"""Support for rasc."""
from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Sequence
import copy
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ACTION_ID,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_PARALLEL,
    CONF_SEQUENCE,
    CONF_SERVICE,
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
)
from homeassistant.core import Event, HomeAssistant

if TYPE_CHECKING:
    from homeassistant.components.script import BaseScriptEntity
    from homeassistant.helpers.entity_component import EntityComponent

from homeassistant.helpers.rascalscheduler import (
    datetime_to_string,
    generate_duration,
    get_entity_id_from_number,
    get_routine_id,
    string_to_datetime,
)
from homeassistant.helpers.template import device_entities

from .entity import ActionEntity, BaseRoutineEntity, Queue, RoutineEntity
from .log import output_all, set_logger

CONF_ROUTINE_ID = "routine_id"
CONF_STEP = "step"
CONF_ENTITY_REGISTRY = "entity_registry"
CONF_END_VIRTUAL_NODE = "end_virtual_node"

TIMEOUT = 3000  # millisecond


_LOGGER = set_logger()


def create_routine(
    hass: HomeAssistant,
    name: str | None,
    routine_id: str | None,
    action_script: Sequence[dict[str, Any]],
) -> BaseRoutineEntity:
    """Convert the script to the DAG using dfs algorithm."""
    next_parents: list[ActionEntity] = []
    entities: dict[str, ActionEntity] = {}
    config: dict[str, Any] = {}

    # configuration for each node
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

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                routine_id=config[CONF_ROUTINE_ID],
                duration=generate_duration(),
                logger=_LOGGER,
            )

            for entity in next_parents:
                entities[action_id].parents.append(entity)

            for entity in next_parents:
                entity.children.append(entities[action_id])

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
        action_id=None,
        routine_id=config[CONF_ROUTINE_ID],
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
    entities: dict[str, Any],
) -> list[ActionEntity]:
    """Convert the script to the dag using dsf."""

    next_parents = []
    # print("script:", script) chart.save('chart.png')
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
        domain = script[CONF_SERVICE].split(".")[0]
        if domain == DOMAIN_SCRIPT:
            script_component: EntityComponent[BaseScriptEntity] = hass.data[
                DOMAIN_SCRIPT
            ]

            if script_component is not None:
                base_script = script_component.get_entity(list(script.values())[0])
                if base_script is not None and base_script.raw_config is not None:
                    next_parents = parents
                    for item in base_script.raw_config[CONF_SEQUENCE]:
                        leaf_entities = _create_routine(
                            hass, item, config, next_parents, entities
                        )
                        next_parents = leaf_entities
        else:
            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                routine_id=config[CONF_ROUTINE_ID],
                duration=generate_duration(),
                logger=_LOGGER,
            )

            for entity in parents:
                entities[action_id].parents.append(entity)
                entity.children.append(entities[action_id])

            next_parents.append(entities[action_id])

    elif CONF_DELAY in script:
        hours = script[CONF_DELAY]["hours"]
        minutes = script[CONF_DELAY]["minutes"]
        seconds = script[CONF_DELAY]["seconds"]
        milliseconds = script[CONF_DELAY]["milliseconds"]

        delta = timedelta(
            hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
        )

        for entity in parents:
            entity.delay = delta

        next_parents = parents

    else:
        config[CONF_STEP] = config[CONF_STEP] + 1
        action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"

        entities[action_id] = ActionEntity(
            hass=hass,
            action=script,
            action_id=action_id,
            routine_id=config[CONF_ROUTINE_ID],
            duration=generate_duration(),
            logger=_LOGGER,
        )

        for entity in parents:
            entities[action_id].parents.append(entity)
            entity.children.append(entities[action_id])

        next_parents.append(entities[action_id])

    return next_parents


def get_target_entities(hass: HomeAssistant, script: dict[str, Any]) -> list[str]:
    """Get target_entities from script with call service action or device action."""
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


class ActionLockInfo:
    """Class for describe the stats of the secheduled action."""

    def __init__(
        self,
        action_id: str,
        action: ActionEntity,
        action_state: str,
        lock_state: str,
        st: str,
        end: str,
    ) -> None:
        """Init the action info."""
        self.action_id = action_id
        self.action = action
        self.action_state = action_state
        self.lock_state = lock_state
        self.time_range = (st, end)


class LineageTable:
    """Maintains a per-device lineage: the planned transition order of that device's lock.

    locks: the state of the device's lock.
    lock_queues: transition order of the device's lock.
    free slots: a list of available time slots in chronological order.

    """

    def __init__(self) -> None:
        """Initialize linage table entity."""

        # locks: key is the entity_id and value is the routine id that is holding the lock now
        self._locks: dict[str, str | None] = {}

        # lock_queues: key is the entity_id and each element stored in the queue is the action that is holding or waiting for the lock
        self._lock_queues: dict[str, Queue] = {}

        # free_slots: key is the entity_id and each element stored in the queue is a slot from the start time to the end time
        self._free_slots: dict[str, Queue] = {}

    @property
    def locks(self) -> dict[str, str | None]:
        """Get locks."""
        return self._locks

    @property
    def lock_queues(self) -> dict[str, Queue]:
        """Get lock queues."""
        return self._lock_queues

    @property
    def free_slots(self) -> dict[str, Queue]:
        """Get free slots."""
        return self._free_slots

    @free_slots.setter
    def free_slots(self, fs: dict[str, Queue]) -> None:
        """Set free slots."""
        self._free_slots = fs

    def add_entity(self, entity_id: str) -> None:
        """Add the entity to the lineage table."""
        self._locks[entity_id] = None
        self._lock_queues[entity_id] = Queue()
        self._free_slots[entity_id] = Queue({datetime_to_string(datetime.now()): None})

    def delete_entity(self, entity_id: str) -> None:
        """Remove the entity with the entity_id from the lineage table."""
        try:
            del self._lock_queues[entity_id]
            del self._locks[entity_id]
            del self._free_slots[entity_id]
        except KeyError as e:
            raise KeyError(f"While deleting entity {entity_id}in lienage table") from e


class BaseScheduler(ABC):
    """Base class for scheduling policy."""

    _hass: HomeAssistant
    _serialization_order: Queue
    _lineage_table: LineageTable

    def filter_ts(
        self, entity_id: str, now: datetime, free_slots: dict[str, Queue]
    ) -> Queue:
        """Filter the time slots that the end time is not smaller than now."""

        fs = free_slots.get(entity_id)

        if not fs:
            raise ValueError(
                "There should be at least one time slot in each entity's timeline"
            )

        filtered_time_slots: Queue = Queue()
        for start_time, end_time in fs.items():
            if not end_time or string_to_datetime(end_time) > now:
                filtered_time_slots[start_time] = end_time

        return filtered_time_slots

    def remove_time_slots_before_now(
        self, now: datetime, free_slots: dict[str, Queue]
    ) -> None:
        """Remove all time slots from the timelines that have ended before the current time(now)."""
        for entity_id, _ in free_slots.items():
            filtered_time_slots = self.filter_ts(entity_id, now, free_slots)
            start_time, end_time = filtered_time_slots.top()

            # Check if the start time of the first time slot needs to be updated
            if (
                now > string_to_datetime(start_time)
                and datetime_to_string(now) != start_time
            ):
                filtered_time_slots.insert_after(
                    start_time, datetime_to_string(now), end_time
                )
                filtered_time_slots.pop(start_time)

            free_slots[entity_id] = Queue(filtered_time_slots)

        _LOGGER.debug(
            "Remove time slots that are smaller than time %s", datetime_to_string(now)
        )

    def get_first_action_with_acquired_lock(
        self, entity_id: str
    ) -> ActionLockInfo | None:
        """Get the first action with acquired_lock."""
        lock_queue = self._lineage_table.lock_queues.get(entity_id)

        return (
            next(
                (
                    action_info
                    for action_info in lock_queue.values()
                    if action_info.lock_state == LOCK_STATE_ACQUIRED
                ),
                None,
            )
            if lock_queue
            else None
        )

    def get_last_action_with_acquired_lock(
        self, entity_id: str
    ) -> ActionLockInfo | None:
        """Get the last action with acquired_lock."""
        lock_queue = self._lineage_table.lock_queues.get(entity_id)
        return (
            next(
                (
                    action_info
                    for action_info in reversed(list(lock_queue.values()))
                    if action_info.lock_state == LOCK_STATE_ACQUIRED
                ),
                None,
            )
            if lock_queue
            else None
        )

    def get_available_ts(
        self,
        now: datetime,
        free_slots: dict[str, Queue],
        entity_id: str,
        lock_leasing: str,
    ) -> str | None:
        """Get the start time of the first available time slot in the entity."""

        if lock_leasing == "general":
            start_time = self.get_ts_by_general(free_slots, now, entity_id)

        elif lock_leasing == "pre":
            start_time = self.get_ts_by_prelease(free_slots, now, entity_id)

        elif lock_leasing == "post":
            start_time = self.get_ts_by_postlease(free_slots, now, entity_id)

        _LOGGER.debug(
            "The start time of the new time slot for the new action in entity %s is %s",
            entity_id,
            start_time,
        )

        return start_time

    def get_ts_by_general(
        self, free_slots: dict[str, Queue], now: datetime, entity_id: str
    ) -> str | None:
        """Get the time slot in general case."""
        return (
            free_slots[entity_id].end()[0]
            if not self.get_first_action_with_acquired_lock(entity_id)
            else None
        )

    def get_ts_by_prelease(
        self, free_slots: dict[str, Queue], now: datetime, entity_id: str
    ) -> str | None:
        """Find the time slot before the action."""
        action = self.get_first_action_with_acquired_lock(entity_id)

        if not action:
            return free_slots[entity_id].end()[0]

        slot_start = self.find_ts_before_action(action, free_slots[entity_id], now)
        slot_end = free_slots[entity_id].get(slot_start) if slot_start else None

        # Check if there is an available time slot before the action
        if not slot_start or not slot_end:
            _LOGGER.debug(
                "Cannot find the slot before the action. Failed to prelease the lock"
            )
            return None

        # Check if the slot is big enough to place the action

        if (
            slot_start
            and slot_end
            and action
            and action.action.duration
            and (
                string_to_datetime(slot_end) - max(string_to_datetime(slot_start), now)
            ).total_seconds()
            < action.action.duration.total_seconds()
        ):
            _LOGGER.debug(
                "The slot is too small to place the action. Failed to prelease the lock"
            )
            return None

        # Check if the action with the acquired key is running
        if self.action_running(action.action, entity_id, "pre"):
            _LOGGER.debug("The action is running. Failed to prelease the lock")
            return None

        return slot_start

    def find_ts_before_action(
        self, action: ActionLockInfo, free_slots: Queue, now: datetime
    ) -> str | None:
        """Find time slot before action."""
        action_st = action.time_range[0]
        return next(
            (
                st
                for st, end in free_slots.items()
                if end == action_st and string_to_datetime(end) > now
            ),
            None,
        )

    def get_ts_by_postlease(
        self, free_slots: dict[str, Queue], now: datetime, entity_id: str
    ) -> str | None:
        """Find the time slot after the action."""

        action = self.get_last_action_with_acquired_lock(entity_id)

        # Check if the serializability would conflict if post-lease
        if action and self.conflict_serializability(action.action, entity_id):
            _LOGGER.error(
                "Violate seriailzability while placing after the action %s. Failed to post-lease the lock",
                action.action_id,
            )
            return None

        # Check if the action with the acquired key is running
        if action and not self.action_running(action.action, entity_id, "post"):
            _LOGGER.error(
                "The action %s is not running. Failed to post-lease the lock",
                action.action_id,
            )
            return None

        # find the available time slot at the end
        slot_start = free_slots[entity_id].end()[0]

        return slot_start

    def conflict_serializability(self, action: ActionEntity, entity_id: str) -> bool:
        """Check if the serializability conflicts if the new action places after the action."""
        next_action = self._lineage_table.lock_queues[entity_id].next(action.action_id)
        return next_action and next_action.lock_state == LOCK_STATE_LEASED

    def action_running(
        self, action: ActionEntity, entity_id: str, lock_leasing: str
    ) -> bool:
        """Check if action is running."""
        action_info = self._lineage_table.lock_queues[entity_id].get(action.action_id)

        if lock_leasing == "pre":
            return action_info.action_state in (RASC_ACK, RASC_START, RASC_COMPLETE)

        if lock_leasing == "post":
            return action_info.action_state in (RASC_START, RASC_COMPLETE)

        return False

    def schedule_action(
        self,
        slot: tuple[str, str | None],
        action_slot: tuple[str, str],
        free_slots: Queue,
    ) -> str:
        """Insert the action to the current time slot and then return the expected end time of the "action"."""
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
            _LOGGER.debug("Insert in the full time slot")
            free_slots.pop(slot_st)

        elif slot_st == action_st:
            _LOGGER.debug("Insert at the front")
            free_slots.insert_after(slot_st, action_end, slot_end)
            free_slots.pop(slot_st)

        elif slot_end == action_end:
            _LOGGER.debug("Insert at the end")
            free_slots.updateitem(slot_st, action_st)

        else:
            _LOGGER.debug("Insert in the middle")
            free_slots.insert_after(slot_st, action_end, slot_end)
            free_slots.updateitem(slot_st, action_st)

        return action_end

    def schedule_lock(
        self,
        new_action: ActionEntity,
        new_action_slot: tuple[str, str],
        entity_id: str,
        lock_leasing: str,
    ) -> None:
        """Schedule the lock for the routine."""

        if not new_action.action_id:
            return

        new_action_info = ActionLockInfo(
            new_action.action_id,
            new_action,
            RASC_SCHEDULED,
            LOCK_STATE_SCHEDULED,
            new_action_slot[0],
            new_action_slot[1],
        )

        if lock_leasing == "pre":
            action = self.get_first_action_with_acquired_lock(entity_id)
            if action:
                self._lineage_table.lock_queues[entity_id].insert_before(
                    action.action_id, new_action.action_id, new_action_info
                )
            else:
                self._lineage_table.lock_queues[entity_id][
                    new_action.action_id
                ] = new_action_info
        elif lock_leasing in ("post", "general"):
            self._lineage_table.lock_queues[entity_id][
                new_action.action_id
            ] = new_action_info

        _LOGGER.debug(
            "Insert action %s to the lock queue %s", new_action.action_id, entity_id
        )

    def schedule_all_action(
        self,
        action: ActionEntity,
        now: datetime,
        free_slots: dict[str, Queue],
        lock_leasing: str,
    ):
        """Insert action to the free slots at now based on lock leasing approach."""

        if not action.duration:
            return

        target_entities = get_target_entities(action.hass, action.action)
        max_end_time = now

        _LOGGER.debug(
            "Action %s start scheduling at time %s",
            action.action_id,
            datetime_to_string(now),
        )

        for entity in target_entities:
            entity_id = get_entity_id_from_number(action.hass, entity)

            start_time = self.get_available_ts(now, free_slots, entity_id, lock_leasing)
            if not start_time:
                return False, None

            dt_start_time = string_to_datetime(start_time)

            dt_action_st = max(dt_start_time, now)
            dt_action_end = dt_action_st + action.duration
            action_st = datetime_to_string(dt_action_st)
            action_end = datetime_to_string(dt_action_end)

            self.schedule_action(
                (start_time, free_slots[entity_id][start_time]),
                (action_st, action_end),
                free_slots[entity_id],
            )
            self.schedule_lock(action, (action_st, action_end), entity_id, lock_leasing)

            max_end_time = max(max_end_time, dt_action_end)

        return True, max_end_time

    def schedule_routine(
        self, hass: HomeAssistant, routine: RoutineEntity, lock_leasing: str
    ) -> dict[str, Queue] | None:
        """Schedule the routine based on the lock leasing approach."""
        _LOGGER.info(
            "Start scheduling the routine %s. The policy is %s",
            routine.routine_id,
            lock_leasing,
        )

        # Remove available time slots before now
        next_end_time = datetime.now()
        self.remove_time_slots_before_now(next_end_time, self._lineage_table.free_slots)

        # Deep copy the free slots
        tmp_fs = copy.deepcopy(self._lineage_table.free_slots)

        config: dict[str, Any] = {}
        config[CONF_STEP] = -1
        config[CONF_ROUTINE_ID] = routine.routine_id

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

                success, next_end_time = self.schedule_all_action(
                    action, next_end_time, tmp_fs, lock_leasing
                )
            else:
                success, next_end_time = self._schedule_routine(
                    hass, script, config, routine, next_end_time, tmp_fs, lock_leasing
                )

            if not success:
                return None

        return tmp_fs

    def _schedule_routine(
        self,
        hass: HomeAssistant,
        script: dict[str, Any],
        config: dict[str, Any],
        routine: RoutineEntity,
        prev_end_time: datetime,
        free_slots: dict[str, Queue],
        lock_leasing: str,
    ):
        """Schedule the script in the routine based on the lock leasing approach and then update both free slots and lock queues."""
        # print("script:", script)
        next_end_time = prev_end_time

        if CONF_PARALLEL in script:
            for item in list(script.values())[0]:
                success, item_end_time = self._schedule_routine(
                    hass, item, config, routine, prev_end_time, free_slots, lock_leasing
                )
                if not success:
                    return False, None
                next_end_time = max(next_end_time, item_end_time)

        elif CONF_SEQUENCE in script:
            for item in list(script.values())[0]:
                success, next_end_time = self._schedule_routine(
                    hass, item, config, routine, next_end_time, free_slots, lock_leasing
                )
                if not success:
                    return False, None

        elif CONF_SERVICE in script:  # pylint: disable=too-many-nested-blocks
            domain = script[CONF_SERVICE].split(".")[0]
            if domain == DOMAIN_SCRIPT:
                script_component: EntityComponent[BaseScriptEntity] = hass.data[
                    DOMAIN_SCRIPT
                ]

                if script_component:
                    base_script = script_component.get_entity(list(script.values())[0])
                    if base_script and base_script.raw_config:
                        for item in base_script.raw_config[CONF_SEQUENCE]:
                            success, next_end_time = self._schedule_routine(
                                hass,
                                item,
                                config,
                                routine,
                                next_end_time,
                                free_slots,
                                lock_leasing,
                            )
                            if not success:
                                return False, None

            else:
                config[CONF_STEP] = config[CONF_STEP] + 1
                action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
                action = routine.actions[action_id]

                success, next_end_time = self.schedule_all_action(
                    action, next_end_time, free_slots, lock_leasing
                )
                if not success:
                    return False, None

        elif CONF_DELAY in script:
            pass

        else:
            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"
            action = routine.actions[action_id]

            success, next_end_time = self.schedule_all_action(
                action, next_end_time, free_slots, lock_leasing
            )
            if not success:
                return False, None

        return True, next_end_time


class FirstComeFirstServeScheduler(BaseScheduler):
    """Class for fcfs scheduler."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
        serialization_order: Queue,
    ) -> None:
        """Initialize fcfs scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._serialization_order = serialization_order

    # def schedule_routine(
    #     self, hass: HomeAssistant, routine: RoutineEntity, lock_leasing: str
    # ) -> dict[str, Queue] | None:
    #     """Schedule routine."""
    #     return super().schedule_routine(hass, routine, lock_leasing)


class JustInTimeScheduler(BaseScheduler):
    """Class for jit scheduler."""

    def __init__(
        self,
        hass: HomeAssistant,
        lineage_table: LineageTable,
        serialization_order: Queue,
    ) -> None:
        """Initialize jit scheduler."""
        self._hass = hass
        self._lineage_table = lineage_table
        self._serialization_order = serialization_order

    # def schedule_routine(
    #     self, hass: HomeAssistant, routine: RoutineEntity, lock_leasing: str
    # ) -> dict[str, Queue] | None:
    #     """Schedule routine."""
    #     return super().schedule_routine(hass, routine, lock_leasing)


class RascalScheduler:
    """Scheduler decides when routines from wait queue are started, acquired locks, and maintains serialization order."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize rascal scheduler entity."""
        self._hass = hass
        self._lineage_table = LineageTable()
        self._serialization_order: Queue = Queue()
        self._wait_queue: Queue = Queue()
        self._hass.bus.async_listen(RASC_RESPONSE, self.handle_event)
        self._scheduler = self._get_scheduler()
        self._logging = True

    @property
    def lineage_table(self) -> LineageTable:
        """Get lineage table."""
        return self._lineage_table

    @property
    def wait_queue(self) -> Queue:
        """Get wait queue."""
        return self._wait_queue

    def _get_scheduler(self) -> Any:
        """Get scheduler."""
        if SCHEDULING_POLICY in (FCFS, FCFS_POST):
            return FirstComeFirstServeScheduler(
                self._hass, self._lineage_table, self._serialization_order
            )

        if SCHEDULING_POLICY in (JIT):
            return JustInTimeScheduler(
                self._hass, self._lineage_table, self._serialization_order
            )

    def _add_routine_to_serialization_order(
        self, new_routine: RoutineEntity, entity_id: str, lock_leasing: str
    ) -> None:
        """Add routine to the serialization order. The new routine should place before or after the current routine if pre-lease or post-lease."""

        # There is no running routine in the serialization order
        if not self._serialization_order:
            _LOGGER.info(
                "Insert new routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

        # There is at least one running routine in the serialization order
        elif lock_leasing == "general":
            self._add_routine_to_order_by_general(new_routine, entity_id)

        elif lock_leasing == "pre":
            self._add_routine_to_order_by_prelease(new_routine, entity_id)

        elif lock_leasing == "post":
            self._add_routine_to_order_by_postlease(new_routine, entity_id)

        output_all(_LOGGER, serialization_order=self._serialization_order)

    def _add_routine_to_order_by_general(
        self, new_routine: RoutineEntity, entity_id: str
    ) -> None:
        """Add routine to the serialization order by general."""
        if new_routine.routine_id not in self._serialization_order:
            _LOGGER.info(
                "Insert routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

    def _add_routine_to_order_by_prelease(
        self, new_routine: RoutineEntity, entity_id: str
    ) -> None:
        """Add routine to the serialization order by prelease."""
        action = self._get_first_action_with_acquired_lock(entity_id)
        routine_id = get_routine_id(action.action_id) if action else None

        if not action and new_routine.routine_id not in self._serialization_order:
            _LOGGER.info(
                "Insert routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

        elif (
            action
            and new_routine.routine_id not in self._serialization_order
            and routine_id == new_routine.routine_id
        ):
            _LOGGER.info(
                "Insert routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

        elif (
            action
            and new_routine.routine_id not in self._serialization_order
            and routine_id != new_routine.routine_id
        ):
            _LOGGER.info(
                "Insert new routine %s to the serialization order after routine %s",
                new_routine.routine_id,
                routine_id,
            )
            self._serialization_order.insert_before(
                routine_id, new_routine.routine_id, new_routine
            )

        elif (
            action
            and new_routine.routine_id in self._serialization_order
            and routine_id != new_routine.routine_id
        ):
            pos = self._serialization_order.index(routine_id)
            new_pos = self._serialization_order.index(new_routine.routine_id)

            if new_pos < pos:
                _LOGGER.info(
                    "Insert new routine %s to the serialization order after routine %s",
                    new_routine.routine_id,
                    routine_id,
                )
                self._serialization_order.pop(new_routine.routine_id)
                self._serialization_order.insert_after(
                    routine_id, new_routine.routine_id, new_routine
                )

    def _add_routine_to_order_by_postlease(
        self, new_routine: RoutineEntity, entity_id: str
    ) -> None:
        """Add routine to the serialization order by postlease."""
        action = self._get_last_action_with_acquired_lock(entity_id)
        routine_id = get_routine_id(action.action_id) if action else None

        if not action and new_routine.routine_id not in self._serialization_order:
            _LOGGER.info(
                "Insert routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

        elif (
            action
            and new_routine.routine_id not in self._serialization_order
            and routine_id == new_routine.routine_id
        ):
            _LOGGER.info(
                "Insert routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

        elif (
            action
            and new_routine.routine_id not in self._serialization_order
            and routine_id != new_routine.routine_id
        ):
            _LOGGER.info(
                "Insert routine %s to the end of the serialization order",
                new_routine.routine_id,
            )
            self._serialization_order[new_routine.routine_id] = new_routine

        elif (
            action
            and new_routine.routine_id in self._serialization_order
            and routine_id != new_routine.routine_id
        ):
            pos = self._serialization_order.index(routine_id)
            new_pos = self._serialization_order.index(new_routine.routine_id)

            if new_pos < pos:
                _LOGGER.info(
                    "Insert new routine %s to the serialization order after routine %s",
                    new_routine.routine_id,
                    routine_id,
                )
                self._serialization_order.pop(new_routine.routine_id)
                self._serialization_order.insert_after(
                    routine_id, new_routine.routine_id, new_routine
                )

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
                self._lineage_table.lock_queues[entity_id].pop(action.action_id)

    def _add_routine_to_wait_queues(self, routine: RoutineEntity) -> None:
        """Add routine to the wait queue."""
        _LOGGER.info("Add routine %s to the wait queue", routine.routine_id)
        self._wait_queue[routine.routine_id] = routine

    def _remove_routine_from_wait_queue(self, routine_id: str) -> None:
        """Remove routine from the wait queue."""
        _LOGGER.info("Remove routine %s from the wait queue", routine_id)
        self._wait_queue.pop(routine_id)

    def _acquire_routine_locks(self, routine: RoutineEntity, lock_leasing: str) -> None:
        """Acquire all locks for the routine."""

        if not routine.routine_id:
            return

        for action in list(routine.actions.values())[:-1]:
            if not action.action_id:
                return

            target_entities = get_target_entities(self._hass, action.action)
            for entity in target_entities:
                entity_id = get_entity_id_from_number(self._hass, entity)
                self._add_routine_to_serialization_order(
                    routine, entity_id, lock_leasing
                )
                self._acquire_lock(action.action_id, entity_id, lock_leasing)

        _LOGGER.info("Routine %s acquired all the locks", routine.routine_id)
        output_all(
            _LOGGER,
            locks=self._lineage_table.locks,
            lock_queues=self._lineage_table.lock_queues,
            serialization_order=self._serialization_order,
        )

    def _acquire_lock(self, action_id: str, entity_id: str, lock_leasing: str) -> None:
        """Acquire lock for the action (action_id)."""

        # Change the lock holder to the routine
        self._lineage_table.locks[entity_id] = get_routine_id(action_id)

        lease_ac = self._get_first_action_with_acquired_lock(entity_id)

        if (
            lock_leasing == "pre"
            and lease_ac
            and get_routine_id(action_id) != get_routine_id(lease_ac.action_id)
        ):
            self._prelease_lock(get_routine_id(lease_ac.action_id), entity_id)

        elif (
            lock_leasing == "post"
            and lease_ac
            and get_routine_id(action_id) != get_routine_id(lease_ac.action_id)
        ):
            self._postlease_lock(get_routine_id(lease_ac.action_id), entity_id)

        self._update_action_lock_state(action_id, entity_id, LOCK_STATE_ACQUIRED)

    def _prelease_lock(self, routine_id: str, entity_id: str) -> None:
        """Prelease lock for routine."""

        for action_id, _lock_queue in self._lineage_table.lock_queues[
            entity_id
        ].items():
            if get_routine_id(action_id) == routine_id:
                self._update_action_lock_state(action_id, entity_id, LOCK_STATE_LEASED)

    def _postlease_lock(self, routine_id: str, entity_id: str) -> None:
        """Postlease lock for routine."""
        for action_id, _lock_queue in self._lineage_table.lock_queues[
            entity_id
        ].items():
            if get_routine_id(action_id) == routine_id:
                self._update_action_lock_state(
                    action_id, entity_id, LOCK_STATE_RELEASED
                )

    def _release_routine_locks(self, routine: RoutineEntity) -> None:
        """Release all the locks for the routine."""
        _LOGGER.info("Release all locks for the routine %s", routine.routine_id)

        for action in list(routine.actions.values())[:-1]:
            self._release_all_locks(action)

    def _release_all_locks(self, action: ActionEntity) -> None:
        """Release all locks for the action."""
        target_entities = get_target_entities(self._hass, action.action)
        for entity in target_entities:
            entity_id = get_entity_id_from_number(self._hass, entity)
            if not action.action_id:
                return
            if self._lineage_table.locks[entity_id] == get_routine_id(action.action_id):
                self._release_lock(entity_id)

    def _release_lock(self, entity_id: str) -> None:
        """Release the lock for the entity."""
        _LOGGER.info("Release the lock %s", entity_id)
        self._lineage_table.locks[entity_id] = None

    def _get_action(self, action_id: str) -> ActionEntity:
        """Get the active action."""
        return self._serialization_order[get_routine_id(action_id)].actions[action_id]

    def _get_first_action_with_acquired_lock(
        self, entity_id: str
    ) -> ActionLockInfo | None:
        """Get the first action with acquired_lock."""
        lock_queue = self._lineage_table.lock_queues[entity_id]
        return next(
            (
                action_info
                for action_info in lock_queue.values()
                if action_info.lock_state == LOCK_STATE_ACQUIRED
            ),
            None,
        )

    def _get_last_action_with_acquired_lock(
        self, entity_id: str
    ) -> ActionLockInfo | None:
        """Get the last action with acquired_lock."""
        lock_queue = self._lineage_table.lock_queues[entity_id]
        return next(
            (
                action_info
                for action_info in reversed(list(lock_queue.values()))
                if action_info.lock_state == LOCK_STATE_ACQUIRED
            ),
            None,
        )

    def _remove_scheduled_actions(self, routine_id: str) -> None:
        """Remove all scheduled actions for the routine in the lock queues."""

        for _entity_id, lock_queue in self._lineage_table.lock_queues.items():
            for action_id, action_info in lock_queue.items():
                if (
                    action_info.lock_state == LOCK_STATE_SCHEDULED
                    and routine_id == get_routine_id(action_id)
                ):
                    lock_queue.pop(action_id)

    def _schedule_routine(self, routine: RoutineEntity) -> bool:
        """Schedule the routine."""

        if SCHEDULING_POLICY in (FCFS):
            self._schedule_routine_fcfs(routine)

        elif SCHEDULING_POLICY in (FCFS_POST):
            return self._schedule_routine_fcfs_post(routine)

        elif SCHEDULING_POLICY in (JIT):
            return self._schedule_routine_jit(routine)

        return False

    def _schedule_routine_fcfs(self, routine: RoutineEntity) -> bool:
        """Schedule routine with FCFS."""

        if not routine.routine_id:
            return False

        tmp_fs = self._scheduler.schedule_routine(self._hass, routine, "general")
        if tmp_fs:
            self._acquire_routine_locks(routine, "general")
            self._lineage_table.free_slots = tmp_fs
            return True

        self._remove_scheduled_actions(routine.routine_id)
        return False

    def _schedule_routine_fcfs_post(self, routine: RoutineEntity) -> bool:
        """Schedule routine with FCFS_POST."""
        if not routine.routine_id:
            return False

        tmp_fs = self._scheduler.schedule_routine(self._hass, routine, "post")
        if tmp_fs:
            self._acquire_routine_locks(routine, "post")
            self._lineage_table.free_slots = tmp_fs
            return True

        self._remove_scheduled_actions(routine.routine_id)
        return False

    def _schedule_routine_jit(self, routine: RoutineEntity) -> bool:
        """Schedule routine with FCFS_POST."""
        if not routine.routine_id:
            return False

        tmp_fs = self._scheduler.schedule_routine(self._hass, routine, "pre")
        if tmp_fs:
            self._acquire_routine_locks(routine, "pre")
            self._lineage_table.free_slots = tmp_fs
            return True

        self._remove_scheduled_actions(routine.routine_id)

        tmp_fs = self._scheduler.schedule_routine(self._hass, routine, "post")
        if tmp_fs:
            self._acquire_routine_locks(routine, "post")
            self._lineage_table.free_slots = tmp_fs
            return True

        self._remove_scheduled_actions(routine.routine_id)
        return False

    def _eligibility_test(self, routine: RoutineEntity) -> bool:
        """Eligibility test for the routine."""
        _LOGGER.info("Start eligibility test for the routine %s", routine.routine_id)
        return self._schedule_routine(routine)

    def initialize_routine(self, routine: RoutineEntity) -> None:
        """Initialize the triggered routine."""

        if not routine.routine_id:
            return

        if self._eligibility_test(routine):
            _LOGGER.info("Routine %s pass the eligibility test", routine.routine_id)

            output_all(
                _LOGGER,
                locks=self._lineage_table.locks,
                lock_queues=self._lineage_table.lock_queues,
                free_slots=self._lineage_table.free_slots,
                serialization_order=self._serialization_order,
            )

            self._start_routine(routine)
        else:
            _LOGGER.info(
                "Routine %s failed to pass the eligibility test", routine.routine_id
            )
            self._add_routine_to_wait_queues(routine)

    def _start_routine(self, routine: RoutineEntity) -> None:
        """Start the routine."""

        _LOGGER.info("Start the routine %s", routine.routine_id)

        # Start the action that doesn't have the parents
        for action_entity in list(routine.actions.values())[:-1]:
            if not action_entity.parents:
                self._start_action(action_entity)

    def _start_action(self, action: ActionEntity) -> None:
        """Start the action."""
        if action.action_id and self._is_action_ready(action):
            _LOGGER.info("Start the action %s", action.action_id)
            self._hass.async_create_task(action.attach_triggered(log_exceptions=False))

    def _is_action_ready(self, action: ActionEntity) -> bool:
        """Check if routine acquire associated locks to execute the action."""

        if not action.action_id:
            return False

        _LOGGER.debug("Check if action %s is ready", action.action_id)
        output_all(_LOGGER, locks=self._lineage_table.locks)

        entities = get_target_entities(self._hass, action.action)
        for entity in entities:
            entity_id = get_entity_id_from_number(self._hass, entity)
            if self._lineage_table.locks[entity_id] != get_routine_id(action.action_id):
                _LOGGER.error(
                    "Routine failed to get all the locks for the action %s",
                    action.action_id,
                )
                return False

        return True

    async def handle_event(self, event: Event) -> None:
        """Handle event."""
        event_type = event.data.get(CONF_TYPE)
        entity_id = event.data.get(CONF_ENTITY_ID)
        action_id = event.data.get(ATTR_ACTION_ID)

        # Skip the event if the action is manually executed
        if not self._serialization_order or not entity_id or not action_id:
            return

        # Get the running action in the serialization order
        action = self._get_action(action_id)

        if event_type == RASC_COMPLETE:
            # Delay the action
            if action.delay:
                await action.async_delay_step()

            # Emulate action's duration
            # await action_entity.asnyc_duration_step()
            await self._async_wait_until(action_id, entity_id)

            self._update_action_state(action_id, entity_id, RASC_COMPLETE)

            _LOGGER.info("Action %s is completed", action_id)
            output_all(_LOGGER, lock_queues=self._lineage_table.lock_queues)

            if SCHEDULING_POLICY in (FCFS_POST):
                self._start_ready_routines()

            elif SCHEDULING_POLICY in (JIT):
                self._return_lock(action_id, entity_id)
                self._start_ready_routines()

            # Check if the action is completed
            if self._is_all_actions_complete(action):
                _LOGGER.info("Group action %s is completed", action_id)

                self._set_action_completed(action_id)

                self._run_next_action(action)

        else:
            self._update_action_state(action_id, entity_id, str(event_type))

    def _return_lock(self, action_id: str, entity_id: str) -> None:
        """Return lock."""

        next_action = self._lineage_table.lock_queues[entity_id].next(action_id)
        if not next_action:
            return

        if next_action and next_action.lock_state == LOCK_STATE_LEASED:
            self._acquire_lock(next_action.action_id, entity_id, "post")

            cur_action = next_action
            next_action = self._lineage_table.lock_queues[entity_id].next(
                cur_action.action_id
            )
            while next_action and get_routine_id(
                cur_action.action_id
            ) == get_routine_id(next_action.action_id):
                self._update_action_lock_state(
                    next_action.action_id, entity_id, LOCK_STATE_ACQUIRED
                )
                next_action = self._lineage_table.lock_queues[entity_id].next(
                    next_action.action_id
                )

            output_all(
                _LOGGER,
                locks=self._lineage_table.locks,
                lock_queues=self._lineage_table.lock_queues,
            )
            if self._condition_check(cur_action.action):
                self._start_action(cur_action.action)

    def _set_action_completed(self, action_id: str) -> None:
        """Set the action of the entity completed."""
        self._serialization_order.get(get_routine_id(action_id)).actions[
            action_id
        ].action_completed = True

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
        self._lineage_table.lock_queues[entity_id].get(action_id).lock_state = state

    def _update_action_state(
        self, action_id: str, entity_id: str, new_state: str
    ) -> None:
        """Update the action state."""
        self._lineage_table.lock_queues[entity_id].get(
            action_id
        ).action_state = new_state

    async def _async_wait_until(self, action_id: str, entity_id: str) -> None:
        """Wait until the time reaches the end time of the action."""
        action_end = self._lineage_table.lock_queues[entity_id][action_id].time_range[1]
        wait_seconds = (string_to_datetime(action_end) - datetime.now()).total_seconds()

        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    def _is_all_actions_complete(self, action: ActionEntity) -> bool:
        """Check if the action is completed."""
        return all(
            self._lineage_table.lock_queues[
                get_entity_id_from_number(self._hass, entity)
            ][action.action_id].action_state
            == RASC_COMPLETE
            for entity in get_target_entities(self._hass, action.action)
        )

    # continue to do, need to check condition variable
    def _condition_check(self, action: ActionEntity) -> bool:
        """Condition check."""
        return all(parent.action_completed for parent in action.parents)

    def _run_next_action(self, action: ActionEntity) -> None:
        """Run the entity's next action."""
        if not action.routine_id:
            return

        # This is not the end of the routine
        for child in action.children:
            if self._condition_check(child):
                if child.action_id:
                    self._start_action(child)
                else:
                    _LOGGER.info("This is the end of the routine %s", action.routine_id)

                    self._handle_end_of_routine(child)

    def _handle_end_of_routine(self, action: ActionEntity) -> None:
        """Handle the end of the routine."""

        if not action.action_id:
            return

        routine_id = action.routine_id

        if not routine_id:
            return

        self._remove_routine_from_lock_queues(self._serialization_order.get(routine_id))
        self._release_routine_locks(self._serialization_order.get(routine_id))
        self._remove_routine_from_serialization_order(routine_id)

        if SCHEDULING_POLICY in (FCFS):
            self._start_ready_routines()

    def _start_ready_routines(self) -> None:
        """Test and start the ready routine."""
        ready_routines: list[str] = []
        for routine_id in self._wait_queue:
            routine = self._wait_queue[routine_id]
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
            routine = self._wait_queue[routine_id]
            self._remove_routine_from_wait_queue(routine_id)
            self._start_routine(routine)
