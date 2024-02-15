"""Support for rasc."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
import json
import logging
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
    FCFS_POST_LEASE,
    LOCK_STATE_ACQUIRED,
    LOCK_STATE_SCHEDULED,
    RASC_COMPLETE,
    RASC_RESPONSE,
)
from homeassistant.core import Event, HomeAssistant

if TYPE_CHECKING:
    from homeassistant.components.script import BaseScriptEntity
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
CONF_SCHEDULING_POLICY = "scheduling"

TIMEOUT = 3000  # millisecond

_LOGGER = logging.getLogger(__name__)
_LOG_EXCEPTION = logging.ERROR + 1


def create_routine(
    hass: HomeAssistant,
    name: str | None,
    routine_id: str | None,
    action_script: Sequence[dict[str, Any]],
    scheduling_policy: str,
) -> BaseRoutineEntity:
    """Convert the script to the DAG using dfs algorithm."""
    next_parents: list[ActionEntity] = []
    entities: dict[str, ActionEntity] = {}
    config: dict[str, Any] = {}

    # configuration for each node
    config[CONF_STEP] = -1
    config[CONF_ROUTINE_ID] = routine_id
    config[CONF_SCHEDULING_POLICY] = scheduling_policy

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
                action_state=None,
                routine_id=config[CONF_ROUTINE_ID],
                scheduling_policy=scheduling_policy,
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
        action_state=None,
        routine_id=config[CONF_ROUTINE_ID],
        scheduling_policy=scheduling_policy,
        logger=_LOGGER,
    )

    for parent in next_parents:
        parent.children.append(entities[CONF_END_VIRTUAL_NODE])
        entities[CONF_END_VIRTUAL_NODE].parents.append(parent)

    return BaseRoutineEntity(name, routine_id, entities, scheduling_policy)


def _create_routine(
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
                action_state=None,
                routine_id=config[CONF_ROUTINE_ID],
                scheduling_policy=config[CONF_SCHEDULING_POLICY],
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
            scheduling_policy=config[CONF_SCHEDULING_POLICY],
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
                target_entities += [
                    async_get_entity_id_from_number(hass, entity)
                    for entity in script[CONF_TARGET][CONF_ENTITY_ID]
                ]
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
        """Add the action to the ready queues."""
        target_entities = get_target_entities(action_entity.hass, action_entity.action)

        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(action_entity.hass, entity)
            self._ready_queues[entity_id][
                action_entity.action_id
            ] = LOCK_STATE_SCHEDULED

    def _remove_action(self, entity_id: str, action_id: str) -> None:
        """Remove the action from the ready queues."""
        try:
            del self.ready_queues[entity_id][action_id]
        except (KeyError, ValueError):
            _LOGGER.exception(
                "While removing action %s from ready queues %s", action_id, entity_id
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
        self._ready_queues: dict[
            str, Queue
        ] = {}  # {entity_id, {action_id, lock_state}}
        self._locks: dict[str, str | None] = {}  # {entity_id, routine_id}

    def add_entity(self, entity_id: str) -> None:
        """Add the entity to the lienage table."""
        self._ready_queues[entity_id] = Queue()
        self._locks[entity_id] = None

    def delete_entity(self, entity_id: str) -> None:
        """Delete the entity in the lienage table."""
        try:
            del self._ready_queues[entity_id]
            del self._locks[entity_id]
        except (KeyError, ValueError):
            _LOGGER.exception("While deleting entity %s in lienage table", entity_id)

    def add_action(self, action_entity: ActionEntity) -> None:
        """Add the action to the lineage table."""
        return super()._add_action(action_entity)

    def remove_action(self, entity_id: str, action_id: str) -> None:
        """Remove the action from the lineage table."""
        return super()._remove_action(entity_id, action_id)

    def output_ready_queues(self) -> None:
        """Output the ready routines."""
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
        """Output the locks."""
        locks = []
        for entity_id, routine_id in self._locks.items():
            entity_json = {"entity_id": entity_id, "routine_id": routine_id}
            locks.append(entity_json)

        out = {"Type": "Locks", "locks": locks}
        print(json.dumps(out, indent=2))  # noqa: T201


class RascalSchedulerEntity(BaseReadyQueues):
    """Scheduler decides when routines from wait queue are started, acquired locks, and maintains serialization order."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize rascal scheduler entity."""
        self._hass = hass
        self._lienage_table = LinageTable()
        self._serialization_order: Queue = Queue()
        self._wait_queues: Queue = Queue()
        self._hass.bus.async_listen(RASC_RESPONSE, self.handle_event)

    @property
    def lienage_table(self) -> LinageTable:
        """Get lienage table."""
        return self._lienage_table

    @property
    def wait_queues(self) -> Queue:
        """Get wait queue."""
        return self._wait_queues

    def _add_routine_to_serialization_order(self, routine: RoutineEntity) -> None:
        """Add the routine to the serialization order queue."""
        self._serialization_order[routine.routine_id] = routine

    def _remove_routine_from_serialization_order(self, routine: RoutineEntity) -> None:
        """Remove the routine from the serialization order."""
        try:
            del self._serialization_order[routine.routine_id]
        except (KeyError, ValueError):
            _LOGGER.exception(
                "While removing routine %s from serialization order", routine.routine_id
            )

    def _add_routine_to_wait_queues(self, routine: RoutineEntity) -> None:
        """Add the routine to the wait queues."""
        self._wait_queues[routine.routine_id] = routine

    def _remove_routine_from_wait_queues(self, routine_id: str) -> None:
        """Remove the routine from the wait queues."""
        del self._wait_queues[routine_id]

    def _add_routine_to_ready_queues(self, routine: RoutineEntity) -> None:
        """Add the routine to the ready queues."""
        for action_entity in list(routine.actions.values())[:-1]:
            self._lienage_table.add_action(action_entity)

    def _get_next_routine(self) -> RoutineEntity | None:
        """Get the next routine from the wait queues."""
        routine_id, routine = self._wait_queues.next()
        return routine if routine_id else None

    def _get_action(self, action_id: str) -> ActionEntity | None:
        """Get the active action from the entity's ready queue."""

        try:
            routine_id = async_get_routine_id(action_id)
            return self._serialization_order[routine_id].actions[action_id]
        except (KeyError, ValueError):
            _LOGGER.exception(
                "While getting active action %s from serialization order", action_id
            )
            return None

    def _acquire_routine_locks(self, routine: RoutineEntity) -> bool:
        """Acquire all locks for the routine."""
        if not routine.routine_id:
            return False

        for action_entity in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action_entity.action)

            # Try to acquire all locks for the target entities
            if not self._acquire_all_locks(
                target_entities, action_entity, routine.routine_id
            ):
                return False

        return True

    def _acquire_all_locks(
        self, entities: list[str], action_entity: ActionEntity, routine_id: str
    ) -> bool:
        """Acquire all locks for the entities in the action_entity."""

        # Track entities that successfully acquired locks
        locked_entities: list[str] = []

        for entity in entities:
            entity_id = async_get_entity_id_from_number(self._hass, entity)

            # Release all acquired locks if acquisition fails for any entity
            if not self._acquire_lock(entity_id, routine_id):
                self._release_all_locks(locked_entities)
                return False

            locked_entities.append(entity_id)

        # If entities acquire all the locks, update the lock states in the ready queues for all entities
        self._update_action_lock_state_in_ready_queues(
            action_entity, LOCK_STATE_ACQUIRED
        )
        return True

    def _acquire_lock(self, entity_id: str, routine_id: str) -> bool:
        """Try to attempt the entity's lock for the routine)."""
        try:
            # Return true if the lock is available or the lock is accessing by the routine itself
            if self._lienage_table.locks.get(entity_id) == routine_id:
                return True

            if not self._lienage_table.locks.get(entity_id):
                next_action_id, _ = self._lienage_table.ready_queues[entity_id].next()

                if (
                    not next_action_id
                    or async_get_routine_id(next_action_id) == routine_id
                ):
                    self._lienage_table.locks[entity_id] = routine_id
                    return True

        except (KeyError, ValueError):
            _LOGGER.exception("While getting lock %s", entity_id)

        return False

    def _release_routine_locks(self, routine: RoutineEntity) -> None:
        """Release all the locks for the routine."""

        for action_entity in list(routine.actions.values())[:-1]:
            target_entities = get_target_entities(self._hass, action_entity.action)
            self._release_all_locks(target_entities)

        ready_routines: list[str] = []
        for routine_id in self._wait_queues:
            routine = self._wait_queues[routine_id]
            if self._acquire_routine_locks(routine):
                ready_routines.append(routine_id)

        for routine_id in ready_routines:
            routine = self._wait_queues[routine_id]
            self._remove_routine_from_wait_queues(routine_id)
            self._start_routine(routine)

    def _release_all_locks(self, entities: list[str]) -> None:
        """Release all the locks for the entities."""
        for entity in entities:
            entity_id = async_get_entity_id_from_number(self._hass, entity)
            self._release_lock(entity_id, False)

    def _release_lock(self, entity_id: str, post_lease: bool) -> None:
        """Release the entity's lock."""
        self._lienage_table.locks[entity_id] = None

        # Move the lock to the next aciton in the entity's ready queue.
        if post_lease:
            self.post_lease(entity_id)

    def _update_action_lock_state_in_ready_queues(
        self, action_entity: ActionEntity, state: str
    ) -> None:
        """Update the lock state for the action in ready queues."""
        target_entities = get_target_entities(self._hass, action_entity.action)
        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(self._hass, entity)
            self._lienage_table.ready_queues[entity_id][action_entity.action_id] = state

    def initialize_routine(self, routine: RoutineEntity) -> None:
        """Initialize the triggered routine."""

        # Add all the actions in the routine in the associated ready queue.
        self._add_routine_to_ready_queues(routine)

        # If the routine can require all the locks right now, start the routine, else
        # Put the routine to the wait queues.
        if self._acquire_routine_locks(routine):
            self._start_routine(routine)
        else:
            # print("add routine to queue", routine.routine_id)
            self._add_routine_to_wait_queues(routine)

    def _start_routine(self, routine: RoutineEntity) -> None:
        """Start the routine."""
        # print("start routine", routine.routine_id)
        # Add the routine to the serialization order.
        self._add_routine_to_serialization_order(routine)

        # Start the action that doesn't have the parents
        for action_entity in list(routine.actions.values())[:-1]:
            if not action_entity.parents:
                self._start_action(action_entity)

    def _start_action(self, action_entity: ActionEntity) -> None:
        """Start the action."""

        if action_entity.action_id:
            self._hass.async_create_task(
                action_entity.attach_triggered(log_exceptions=False)
            )

    async def handle_event(self, event: Event) -> None:
        """Handle event."""
        event_type = event.data.get(CONF_TYPE)
        entity_id = event.data.get(CONF_ENTITY_ID)
        action_id = event.data.get(ATTR_ACTION_ID)
        # Skip the event if the action is manually executed
        if not self._serialization_order or not entity_id or not action_id:
            return

        # Get the active action in the entity's ready queue.
        action_entity = self._get_action(action_id)
        if not action_entity:
            return

        if event_type == RASC_COMPLETE:
            # Delay the action
            if action_entity.delay:
                await action_entity.async_delay_step()

            # Check if the action is completed.
            self._lienage_table.remove_action(entity_id, action_id)

            if self._action_complete(action_entity):
                self._update_action_state(action_entity, RASC_COMPLETE)

                if action_entity.scheduling_policy == FCFS_POST_LEASE:
                    self._release_lock(entity_id, True)

                self._run_next_action(action_entity)

        else:
            self._update_action_state(action_entity, str(event_type))

    def _update_action_state(self, action_entity: ActionEntity, new_state: str) -> None:
        """Update the action state."""
        action_entity.action_state = new_state

    def _action_complete(self, action_entity: ActionEntity) -> bool:
        """Check if the action is completed."""
        target_entities = get_target_entities(self._hass, action_entity.action)

        for entity in target_entities:
            entity_id = async_get_entity_id_from_number(self._hass, entity)

            for action_id in self._lienage_table.ready_queues[entity_id]:
                if action_id == action_entity.action_id:
                    return False

        return True

    # continue to do, need to check condition variable
    def _condition_check(self, action_entity: ActionEntity) -> bool:
        """Condition check."""
        for parent in action_entity.parents:
            if parent.action_state != RASC_COMPLETE:
                return False

        return True

    def _run_next_action(self, action_entity: ActionEntity) -> None:
        """Run the entity's next action."""
        for child in action_entity.children:
            if self._condition_check(child):
                if child.action_id:
                    self._start_action(child)
                else:
                    _LOGGER.info(
                        "This is the end of the routine %s", action_entity.routine_id
                    )

                    # Update the action state to RASC_COMPLETE
                    self._update_action_state(child, RASC_COMPLETE)

                    # Release all the locks held by the routine
                    self._release_routine_locks(
                        self._serialization_order[action_entity.routine_id]
                    )

                    # Remove the routine from the serialization order
                    self._remove_routine_from_serialization_order(
                        self._serialization_order[action_entity.routine_id]
                    )

    def post_lease(self, entity_id: str):
        """Post lease."""

        next_action_id, next_lock_state = self._lienage_table.ready_queues[
            entity_id
        ].next()

        if not next_action_id or next_lock_state == LOCK_STATE_ACQUIRED:
            return

        try:
            routine_id = async_get_routine_id(next_action_id)
            routine = self._wait_queues[routine_id]

            if self._acquire_routine_locks(routine):
                self._remove_routine_from_wait_queues(routine_id)
                self._start_routine(routine)
        except (KeyError, ValueError):
            _LOGGER.exception("While post leasing lock %s", entity_id)

    def output_wait_queues(self) -> None:
        """Output wait queues."""
        routines = []
        for routine_id in self._wait_queues:
            routines.append(routine_id)

        out = {"Type": "Wait Queues", "routines": routines}
        print(json.dumps(out, indent=2))  # noqa: T201

    def output_serialization_order(self) -> None:
        """Output serialization order."""
        routines = []
        for routine_id in self._serialization_order:
            routines.append(routine_id)

        out = {"Type": "Serialization Order", "routines": routines}
        print(json.dumps(out, indent=2))  # noqa: T201()
