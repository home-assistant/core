"""Support for rasc."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
import json
import logging
from typing import Any

from homeassistant.components.script import BaseScriptEntity
from homeassistant.const import (
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_PARALLEL,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_TARGET,
    CONF_TYPE,
    DOMAIN_SCRIPT,
    LOCK_STATE_ACQUIRED,
    LOCK_STATE_SCHEDULED,
    RASC_ACK,
    RASC_COMPLETE,
    RASC_RESPONSE,
    RASC_START,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.rascalscheduler import (
    async_get_entity_id_from_number,
    async_get_routine_id,
)
from homeassistant.helpers.template import device_entities

from .entity import ActionEntity, BaseRoutineEntity, Queue, RoutineEntity

CONF_ROUTINE_ID = "routine_id"
CONF_STEP = "step"
CONF_ENTITY_REGISTRY = "entity_registry"
CONF_END_VIRTUAL_NODE = "end_virtual_node"

TIMEOUT = 3000  # millisecond

_LOGGER = logging.getLogger(__name__)
_LOG_EXCEPTION = logging.ERROR + 1


def create_routine(
    hass: HomeAssistant,
    name: str | None,
    routine_id: str | None,
    action_script: Sequence[dict[str, Any]],
) -> BaseRoutineEntity:
    """Convert the script to the DAG using dsf algorithm."""
    next_parents: list[ActionEntity] = []
    entities: dict[str, ActionEntity] = {}
    config: dict[str, Any] = {}

    # configuration for each node
    config[CONF_STEP] = -1
    config[CONF_ROUTINE_ID] = routine_id

    for _, script in enumerate(action_script):
        # print("script:", script)
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
                action_state=None,
                routine_id=config[CONF_ROUTINE_ID],
                logger=_LOGGER,
            )

            for entity in next_parents:
                entities[action_id].parents.append(entity)

            for entity in next_parents:
                entity.children.append(entities[action_id])

            next_parents.clear()
            next_parents.append(entities[action_id])

        else:
            leaf_nodes = dfs(hass, script, config, next_parents, entities)
            next_parents.clear()
            next_parents = leaf_nodes

    # add virtual node to the end of the routine
    # the use of the virtual node is to identify if all actions in the routine are completed
    entities[CONF_END_VIRTUAL_NODE] = ActionEntity(
        hass=hass,
        action={},
        action_id=None,
        action_state=None,
        routine_id=config[CONF_ROUTINE_ID],
        logger=_LOGGER,
    )

    for parent in next_parents:
        parent.children.append(entities[CONF_END_VIRTUAL_NODE])
        entities[CONF_END_VIRTUAL_NODE].parents.append(parent)

    return BaseRoutineEntity(
        name,
        routine_id,
        entities,
    )


def dfs(
    hass: HomeAssistant,
    script: dict[str, Any],
    config: dict[str, Any],
    parents: list[ActionEntity],
    entities: dict[str, Any],
) -> list[ActionEntity]:
    """Convert the script to the dag using dsf."""

    next_parents = []
    # print("script:", script)
    if CONF_PARALLEL in script:
        for item in list(script.values())[0]:
            leaf_entities = dfs(hass, item, config, parents, entities)
            for entity in leaf_entities:
                next_parents.append(entity)

    elif CONF_SEQUENCE in script:
        next_parents = parents
        for item in list(script.values())[0]:
            leaf_entities = dfs(hass, item, config, next_parents, entities)
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
                        leaf_entities = dfs(hass, item, config, next_parents, entities)
                        next_parents = leaf_entities
        else:
            target_entities = get_target_entities(hass, script)

            config[CONF_STEP] = config[CONF_STEP] + 1
            action_id = f"{config[CONF_ROUTINE_ID]}.{config[CONF_STEP]}"

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                action_state=None,
                routine_id=config[CONF_ROUTINE_ID],
                group=len(target_entities) > 1,
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
            action_state=None,
            routine_id=config[CONF_ROUTINE_ID],
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
                async_get_entity_id_from_number(hass, entity)
                for device_id in device_ids
                for entity in device_entities(hass, device_id)
            ]

        if CONF_ENTITY_ID in script[CONF_TARGET]:
            if isinstance(script[CONF_TARGET][CONF_ENTITY_ID], str):
                target_entities += [
                    async_get_entity_id_from_number(
                        hass, script[CONF_TARGET][CONF_ENTITY_ID]
                    )
                ]
            else:
                target_entities += async_get_entity_id_from_number(
                    hass, script[CONF_TARGET][CONF_ENTITY_ID]
                )
    else:
        target_entities = [
            async_get_entity_id_from_number(hass, script[CONF_ENTITY_ID])
        ]

    return target_entities


class BaseReadyQueues:
    """Base class for ready queue."""

    _ready_queues: dict[str, Queue]

    @property
    def ready_queues(self) -> dict[str, Queue]:
        """Get ready routines."""
        return self._ready_queues

    def _add_action(self, action_entity: ActionEntity) -> None:
        """Add action."""
        hass = action_entity.hass
        target_entities = get_target_entities(hass, action_entity.action)

        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(hass, entity)

            try:
                self._ready_queues[entity_id][
                    action_entity.action_id
                ] = LOCK_STATE_SCHEDULED
            except (KeyError, ValueError):
                _LOGGER.exception(
                    "While adding action %s to ready queue %s ",
                    action_entity.action_id,
                    entity_id,
                )

    def _remove_action(self, hass: HomeAssistant, action_entity: ActionEntity) -> None:
        """Remove action."""
        target_entities = get_target_entities(hass, action_entity.action)

        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(hass, entity)

            try:
                del self._ready_queues[entity_id][action_entity.action_id]
            except (KeyError, ValueError):
                _LOGGER.exception(
                    "While removing action %s from ready queue %s",
                    action_entity.action_id,
                    entity_id,
                )


class BaseLocks:
    """Base clocks."""

    _locks: dict[str, str | None] = {}

    @property
    def locks(self) -> dict[str, str | None]:
        """Get locks."""
        return self._locks


class LinageTable(BaseLocks, BaseReadyQueues):
    """Maintains a per-device lineage: the planned transition order of that device's lock.

    ready_queues: transition order of the device's lock.
    locks: the state of the device's lock

    """

    def __init__(self) -> None:
        """Initialize linage table entity."""
        self._ready_queues: dict[str, Queue] = {}  # {action_id, lock_state}
        self._locks: dict[str, str | None] = {}  # {entity_id, routine_id}

    def add_entity(self, entity_id: str) -> None:
        """Add entity (entity_id) to lienage table."""
        self._ready_queues[entity_id] = Queue()
        self._locks[entity_id] = None

    def delete_entity(self, entity_id: str) -> None:
        """Delete entity (entity_id) in lienage table."""
        try:
            del self._ready_queues[entity_id]
            del self._locks[entity_id]
        except (KeyError, ValueError):
            _LOGGER.exception("While deleting entity %s in lienage table", entity_id)

    def add_action(self, action_entity: ActionEntity) -> None:
        """Add action."""
        return super()._add_action(action_entity)

    def remove_action(self, hass: HomeAssistant, action_entity: ActionEntity) -> None:
        """Remove action."""
        return super()._remove_action(hass, action_entity)

    def output_ready_queues(self) -> None:
        """Output the content of ready routines."""
        ready_routines = []
        for entity_id, actions in self._ready_queues.items():
            action_list = []
            for action_id in actions:
                sub_entity_json = {
                    "action_id": action_id,
                    "lock_state": actions[action_id],
                }
                action_list.append(sub_entity_json)

            entity_json = {"entity_id": entity_id, "actions": action_list}

            ready_routines.append(entity_json)

        out = {"Type": "Ready Routines", "Routines": ready_routines}
        print(json.dumps(out, indent=2))  # noqa: T201

    def output_locks(self) -> None:
        """Out locks."""
        locks = []
        for entity_id, routine_id in self._locks.items():
            entity_json = {"entity_id": entity_id, "routine_id": routine_id}
            locks.append(entity_json)

        out = {"Type": "Locks", "locks": locks}
        print(json.dumps(out, indent=2))  # noqa: T201


class RascalSchedulerEntity(BaseReadyQueues):
    """Representation of a rascal scehduler entity.

    Scheduler decides when routines from wait queue are started, acquired locks, and maintains serialization order.

    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize rascal scheduler entity."""
        self._hass = hass
        self._lienage_table = LinageTable()
        self._serialization_order: Queue = Queue()
        self._wait_queues: list[RoutineEntity] = []
        self._hass.bus.async_listen(RASC_RESPONSE, self.handle_event)

    @property
    def lienage_table(self) -> LinageTable:
        """Get lienage table."""
        return self._lienage_table

    @property
    def wait_queues(self) -> list[RoutineEntity]:
        """Get wait queue."""
        return self._wait_queues

    def _add_routine_to_serialization_order(self, routine: RoutineEntity) -> None:
        """Add routine to serialization order."""
        self._serialization_order[routine.routine_id] = routine

    def _remove_routine_from_serialization_order(self, routine: RoutineEntity) -> None:
        """Remove routine from serialization order."""
        try:
            del self._serialization_order[routine.routine_id]
        except (KeyError, ValueError):
            _LOGGER.exception(
                "While removing routine %s from serialization order", routine.routine_id
            )

    def _add_routine_to_wait_queues(self, routine: RoutineEntity) -> None:
        """Add routine to wait queues."""
        self._wait_queues.append(routine)

    def _add_routine_to_ready_queues(self, routine: RoutineEntity) -> None:
        """Add routine to ready queues."""
        for action_entity in routine.actions.values():
            if action_entity.action_id is not None:
                self._lienage_table.add_action(action_entity)

    def _get_next_routine(self) -> RoutineEntity | None:
        """Get next routine from wait queues."""
        if self._wait_queues:
            return self._wait_queues[0]
        return None

    def _get_active_action(self, entity_id: str) -> ActionEntity | None:
        """Get active action from the entity. The active action is the first action in the ready queue with entity_id."""

        action_id, _ = self._lienage_table.ready_queues[entity_id].next()

        if action_id is not None:
            routine_id = async_get_routine_id(action_id)

            try:
                return self._serialization_order[routine_id][action_id]
            except (KeyError, ValueError):
                _LOGGER.exception(
                    "While getting active action %s from serialization order", action_id
                )
        else:
            _LOGGER.error(
                "While getting active action %s from serialization order", action_id
            )

        return None

    def _attempt_lock(self, entity_id: str, routine_id: str) -> bool:
        """Try to acquire the lock of entity (entity_id)."""
        try:
            return (
                self._lienage_table.locks[entity_id] is None
                or self._lienage_table.locks[entity_id] == routine_id
            )
        except (KeyError, ValueError):
            _LOGGER.exception("While getting lock %s", entity_id)

        return False

    def _release_lock(self, entity_id: str) -> None:
        """Release lock."""
        try:
            self._lienage_table.locks[entity_id] = None
        except (KeyError, ValueError):
            _LOGGER.exception("While getting lock %s", entity_id)

    def _acquire_locks(self, action_entity: ActionEntity) -> None:
        """Acquire lock for the action."""
        if action_entity.action_id is not None:
            target_entities = get_target_entities(self._hass, action_entity.action)

            for entity in target_entities:
                entity_id = async_get_entity_id_from_number(self._hass, entity)

                try:
                    routine_id = async_get_routine_id(action_entity.action_id)
                    self._lienage_table.locks[entity_id] = routine_id
                    self._update_action_lock_state_in_ready_queues(
                        action_entity, LOCK_STATE_ACQUIRED
                    )
                except (KeyError, ValueError):
                    _LOGGER.exception("While getting lock %s", entity_id)

    def _attempt_routine_locks(self, routine: RoutineEntity) -> bool:
        """Try to acquire all locks for the routine."""
        if routine.routine_id is not None:
            return all(
                self._attempt_lock(entity_id, routine.routine_id)
                for action_entity in routine.actions.values()
                if action_entity.action_id is not None
                for entity_id in get_target_entities(self._hass, action_entity.action)
            )

        return False

    def _acquire_routine_locks(self, routine: RoutineEntity) -> None:
        """Acquire all locks for the routine."""
        for action_entity in routine.actions.values():
            if action_entity.action_id is not None:
                self._acquire_locks(action_entity)

    def _release_routine_locks(self, routine: RoutineEntity) -> None:
        """Release routine's locks."""
        for action_entity in routine.actions.values():
            if action_entity is not None:
                self._release_action_locks(action_entity)

    def _release_action_locks(self, action_entity: ActionEntity) -> None:
        """Release action's locks."""
        if action_entity.action_id is not None:
            target_entities = get_target_entities(self._hass, action_entity.action)
            for entity in target_entities:
                entity_id = async_get_entity_id_from_number(self._hass, entity)
                self._release_lock(entity_id)

    def _update_action_lock_state_in_ready_queues(
        self, action_entity: ActionEntity, state: str
    ) -> None:
        """Update lock state to new_lock_state."""
        target_entities = get_target_entities(self._hass, action_entity.action)
        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(self._hass, entity)
            self._lienage_table.ready_queues[entity_id][action_entity.action_id] = state

    def init_routine(self, routine: RoutineEntity) -> None:
        """Init routine."""

        self._add_routine_to_ready_queues(routine)

        if self._attempt_routine_locks(routine) and not self._wait_queues:
            self._acquire_routine_locks(routine)
            self._start_routine(routine)
        else:
            self._add_routine_to_wait_queues(routine)

    def _start_routine(self, routine: RoutineEntity) -> None:
        """Start routine."""

        self._add_routine_to_serialization_order(routine)

        self._lienage_table.output_ready_queues()
        self._lienage_table.output_locks()

        for action_entity in routine.actions.values():
            if action_entity.action_id is not None and not action_entity.parents:
                self._start_action(action_entity)

    def _start_action(self, action_entity: ActionEntity) -> None:
        """Start the action."""

        if action_entity.action_id is not None:
            self._hass.async_create_task(
                action_entity.attach_triggered(log_exceptions=False)
            )

    async def handle_event(self, event: Event) -> None:
        """Handle event."""
        event_type = event.data.get(CONF_TYPE)
        entity_id = event.data.get(CONF_ENTITY_ID)

        if entity_id is not None:
            action_entity = self._get_active_action(str(entity_id))

        if action_entity is not None:
            if event_type == RASC_COMPLETE:
                if action_entity.delay is not None:
                    await action_entity.async_delay_step()

                if not action_entity.group or self.is_group_action_complete(
                    action_entity
                ):
                    self._update_action_state(action_entity, RASC_COMPLETE)
                    self._lienage_table.remove_action(self._hass, action_entity)

                    self._run_next_action(action_entity)

            elif event_type == RASC_START:
                self._update_action_state(action_entity, RASC_START)

            elif event_type == RASC_ACK:
                self._update_action_state(action_entity, RASC_ACK)

        else:
            _LOGGER.error("Failed to find the active action")

    def _update_action_state(self, action_entity: ActionEntity, new_state: str) -> None:
        """Update action state to new state."""
        action_entity.action_state = new_state

    def is_group_action_complete(self, action_entity: ActionEntity) -> bool:
        """Check if the group command are completed."""
        target_entities = get_target_entities(self._hass, action_entity.action)

        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(self._hass, entity)

            if action_entity.action_id in self._lienage_table.ready_queues[entity_id]:
                return False

        return True

    # continue to do, need to check condition variable
    def condition_check(self, action_entity: ActionEntity) -> bool:
        """Condition check."""
        for parent in action_entity.parents:
            if parent.action_state != RASC_COMPLETE:
                return False

        return True

    def _run_next_action(self, action_entity: ActionEntity) -> None:
        """Run the next action for action_entity."""
        for child in action_entity.children:
            if child.action_id is not None:
                if self.condition_check(child):
                    self._start_action(child)
            else:
                _LOGGER.info("This is the end of the routine")
                self._release_routine_locks(
                    self._serialization_order[action_entity.routine_id]
                )
                self._remove_routine_from_serialization_order(
                    self._serialization_order[action_entity.routine_id]
                )
                self._schedule_next_routine()

    def _schedule_next_routine(self) -> None:
        """Schedule the next routine based on FIFO."""
        if self._wait_queues:
            routine_entity = self._get_next_routine()

            if routine_entity is not None:
                if self._attempt_routine_locks(routine_entity):
                    self._acquire_routine_locks(routine_entity)
                    self._start_routine(routine_entity)
                else:
                    _LOGGER.error("Failed to schedule the next routine")

    def post_lease(self, entity_id: str) -> None:
        """Post lease."""
        self._release_lock(entity_id)
        action_id, _ = self._lienage_table.ready_queues[entity_id].next()

        if action_id is not None:
            routine_id = async_get_routine_id(action_id)
            self._update_action_lock_state_in_ready_queues(
                self._serialization_order[routine_id].actions[action_id],
                LOCK_STATE_ACQUIRED,
            )

            self._lienage_table.locks[entity_id] = routine_id

            next_routine = self._get_next_routine()
            if next_routine is not None:
                if self._attempt_routine_locks(self._serialization_order[routine_id]):
                    self._acquire_routine_locks(self._serialization_order[routine_id])
                    self._start_routine(next_routine)
