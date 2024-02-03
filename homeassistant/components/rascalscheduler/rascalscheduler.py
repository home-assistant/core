"""Support for rasc."""
# from __future__ import annotations

# from collections.abc import Sequence
# from datetime import timedelta
# import json, logging
# from typing import Any

# from homeassistant.components.script import BaseScriptEntity
# from homeassistant.const import (
#     CONF_DELAY,
#     CONF_DEVICE_ID,
#     CONF_ENTITY_ID,
#     CONF_PARALLEL,
#     CONF_SEQUENCE,
#     CONF_SERVICE,
#     CONF_TARGET,
#     CONF_TYPE,
#     DOMAIN_RASCALSCHEDULER,
#     DOMAIN_SCRIPT,
#     RASC_COMPLETE,
#     RASC_RESPONSE,
#     RASC_START,
#     LOCK_STATE_ACQUIRED,
#     LOCK_STATE_RELEASED
# )
# from homeassistant.core import Event, HomeAssistant
# from homeassistant.helpers.entity_component import EntityComponent
# from .entity import (
#     ActionEntity,
#     QueueEntity,
#     RoutineEntity,
#     OrderedQueueEntity,
#     async_get_entity_id_from_action_entity,
#     async_get_entity_id_from_number
# )
# from homeassistant.helpers.template import device_entities

# CONF_ROUTINE_ID = "routine_id"
# CONF_STEP = "step"
# CONF_HASS = "hass"
# CONF_ENTITY_REGISTRY = "entity_registry"
# CONF_LOGGER = "logger"
# CONF_END_VIRTUAL_NODE = "end_virtual_node"


# TIMEOUT = 3000  # millisecond

# _LOGGER = logging.getLogger(__name__)
# _LOG_EXCEPTION = logging.ERROR + 1


# def setup_rascal_scheduler_entity(hass: HomeAssistant) -> None:
#     """Set up RASC scheduler entity."""
#     _LOGGER.info("Setup rascal entity")
#     hass.data[DOMAIN_RASCALSCHEDULER] = RascalSchedulerEntity(hass)
#     hass.bus.async_listen(
#         RASC_RESPONSE, hass.data[DOMAIN_RASCALSCHEDULER].event_listener
#     )


# def get_rascal_scheduler(hass: HomeAssistant) -> RascalSchedulerEntity:
#     """Get rascal scheduler."""
#     scheduler: RascalSchedulerEntity = hass.data[DOMAIN_RASCALSCHEDULER]
#     return scheduler


# def create_routine(
#     hass: HomeAssistant,
#     name: str | None,
#     routine_id: str | None,
#     action_script: Sequence[dict[str, Any]],
# ) -> RoutineEntity:
#     """Convert the script to the DAG using dsf algorithm."""
#     next_parents: list[ActionEntity] = []
#     entities: dict[str, ActionEntity] = {}
#     config: dict[str, Any] = {}

#     # configuration for each node
#     config[CONF_STEP] = -1
#     config[CONF_ROUTINE_ID] = routine_id

#     for _, script in enumerate(action_script):
#         # print("script:", script)
#         if (
#             CONF_PARALLEL not in script
#             and CONF_SEQUENCE not in script
#             and CONF_SERVICE not in script
#             and CONF_DELAY not in script
#         ):
#             # print("script:", script)
#             config[CONF_STEP] = config[CONF_STEP] + 1
#             action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

#             entities[action_id] = ActionEntity(
#                 hass=hass,
#                 action=script,
#                 action_id=action_id,
#                 action_state=None,
#                 lock_state=None,
#                 routine_id=config[CONF_ROUTINE_ID],
#                 logger=_LOGGER,
#             )

#             for entity in next_parents:
#                 entities[action_id].parents.append(entity)

#             for entity in next_parents:
#                 entity.children.append(entities[action_id])

#             next_parents.clear()
#             next_parents.append(entities[action_id])

#         else:
#             leaf_nodes = dfs(hass, script, config, next_parents, entities)
#             next_parents.clear()
#             next_parents = leaf_nodes

#     # add virtual node to the end of the routine
#     # the use of the virtual node is to identify if all actions in the routine are completed
#     entities["end_virtual_node"] = ActionEntity(
#         hass=hass,
#         action={},
#         action_id=None,
#         action_state=None,
#         lock_state=None,
#         routine_id=config[CONF_ROUTINE_ID],
#         logger=_LOGGER,
#     )

#     for parent in next_parents:
#         parent.children.append(entities["end_virtual_node"])
#         entities["end_virtual_node"].parents.append(parent)

#     return RoutineEntity(name, routine_id, entities, TIMEOUT, _LOGGER)


# def dfs(
#     hass: HomeAssistant,
#     script: dict[str, Any],
#     config: dict[str, Any],
#     parents: list[ActionEntity],
#     entities: dict[str, Any],
# ) -> list[ActionEntity]:
#     """Convert the script to the dag using dsf."""

#     next_parents = []
#     # print("script:", script)
#     if CONF_PARALLEL in script:
#         for item in list(script.values())[0]:
#             leaf_entities = dfs(hass, item, config, parents, entities)
#             for entity in leaf_entities:
#                 next_parents.append(entity)

#     elif CONF_SEQUENCE in script:
#         next_parents = parents
#         for item in list(script.values())[0]:
#             leaf_entities = dfs(hass, item, config, next_parents, entities)
#             next_parents = leaf_entities

#     elif CONF_SERVICE in script:
#         domain = script["service"].split(".")[0]
#         if domain == DOMAIN_SCRIPT:
#             script_component: EntityComponent[BaseScriptEntity] = config[
#                 CONF_HASS
#             ].data[DOMAIN_SCRIPT]

#             if script_component is not None:
#                 base_script = script_component.get_entity(list(script.values())[0])
#                 if base_script is not None and base_script.raw_config is not None:
#                     next_parents = parents
#                     for item in base_script.raw_config[CONF_SEQUENCE]:
#                         leaf_entities = dfs(hass, item, config, next_parents, entities)
#                         next_parents = leaf_entities
#         else:
#             target_entities: list[str] = []
#             if CONF_DEVICE_ID in script[CONF_TARGET]:
#                 device_ids = []
#                 if isinstance(script[CONF_TARGET][CONF_DEVICE_ID], str):
#                     device_ids = [script[CONF_TARGET][CONF_DEVICE_ID]]
#                 else:
#                     device_ids = script[CONF_TARGET][CONF_DEVICE_ID]
#                 target_entities += [
#                     entity
#                     for device_id in device_ids
#                     for entity in device_entities(hass, device_id)
#                 ]

#             if CONF_ENTITY_ID in script[CONF_TARGET]:
#                 if isinstance(script[CONF_TARGET][CONF_ENTITY_ID], str):
#                     target_entities += [script[CONF_TARGET][CONF_ENTITY_ID]]
#                 else:
#                     target_entities += script[CONF_TARGET][CONF_ENTITY_ID]

#             config[CONF_STEP] = config[CONF_STEP] + 1
#             action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

#             entities[action_id] = ActionEntity(
#                 hass=hass,
#                 action=script,
#                 action_id=action_id,
#                 action_state=None,
#                 lock_state=None,
#                 routine_id=config[CONF_ROUTINE_ID],
#                 group=len(target_entities) > 1,
#                 logger=_LOGGER,
#             )

#             for entity in parents:
#                 entities[action_id].parents.append(entity)
#                 entity.children.append(entities[action_id])

#             next_parents.append(entities[action_id])
#     elif CONF_DELAY in script:
#         hours = script[CONF_DELAY]["hours"]
#         minutes = script[CONF_DELAY]["minutes"]
#         seconds = script[CONF_DELAY]["seconds"]
#         milliseconds = script[CONF_DELAY]["milliseconds"]

#         delta = timedelta(
#             hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
#         )

#         for entity in parents:
#             entity.delay = delta

#         next_parents = parents

#     else:
#         config[CONF_STEP] = config[CONF_STEP] + 1
#         action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

#         entities[action_id] = ActionEntity(
#             hass=hass,
#             action=script,
#             action_id=action_id,
#             action_state=None,
#             lock_state=None,
#             routine_id=config[CONF_ROUTINE_ID],
#             logger=_LOGGER,
#         )

#         for entity in parents:
#             entities[action_id].parents.append(entity)

#         for entity in parents:
#             entity.children.append(entities[action_id])

#         next_parents.append(entities[action_id])

#     return next_parents


# class BaseActiveRoutines:
#     """Base class for active routines."""

#     _active_routines: dict[str, ActionEntity | None]

#     @property
#     def active_routines(self) -> dict[str, ActionEntity | None]:
#         """Get active routines."""
#         return self._active_routines

#     def output_active_routines(self) -> None:
#         """Output the content of active routines."""
#         active_routines = []
#         for entity_id, action_entity in self._active_routines.items():
#             if action_entity is not None:
#                 entity_json = {
#                     "action_id": action_entity.action_id,
#                     "action": action_entity.action,
#                     "action_state": action_entity.action_state,
#                     "lock_state": action_entity.lock_state,
#                 }

#             else:
#                 entity_json = {
#                     "action_id": "None",
#                     "action_state": "None",
#                 }

#             active_routines.append(entity_json)

#         out = {"Type": "Active Routines", "Routines": active_routines}
#         print(json.dumps(out, indent=2))  # noqa: T201


# class BaseReadyQueues:
#     """Base class for ready queue."""

#     _ready_queues: dict[str, QueueEntity]

#     @property
#     def ready_queues(self) -> dict[str, QueueEntity]:
#         """Get ready routines."""
#         return self._ready_queues

#     def output_ready_queues(self) -> None:
#         """Output the content of ready routines."""
#         ready_routines = []
#         for entity_id, actions in self._ready_queues.items():
#             action_list = []
#             for action_entity in actions:
#                 sub_entity_json = {
#                     "action_id": action_entity.action_id,
#                     "action": action_entity.action,
#                     "action_state": action_entity.action_state,
#                     "lock_state": action_entity.lock_state,
#                 }

#                 action_list.append(sub_entity_json)

#             entity_json = {"entity_id": entity_id, "actions": action_list}

#             ready_routines.append(entity_json)

#         out = {"Type": "Ready Routines", "Routines": ready_routines}
#         print(json.dumps(out, indent=2))  # noqa: T201


# class BaseLocks:

#     _locks: dict[str, RoutineEntity| None] = {}

#     @property
#     def locks(self)-> dict[str, RoutineEntity| None]:
#         return self._locks


# class LinageTable(BaseLocks, BaseReadyQueues):
#     """Maintains a per-device lineage: the planned transition order of that device's lock.

#     ready_queues: transition order of the device's lock.
#     locks: the state of the device's lock

#     """

#     def __init__(self) -> None:
#         """Initialize linage table entity."""
#         self._ready_queues: dict[str, QueueEntity] = {}
#         self._locks: dict[str, RoutineEntity | None] = {}


# class RascalSchedulerEntity(BaseActiveRoutines, BaseReadyQueues):
#     """Representation of a rascal scehduler entity.

#     Scheduler decides when routines from wait queue are started, acquired locks, and maintains serialization order.

#     """

#     def __init__(self, hass: HomeAssistant) -> None:
#         """Initialize rascal scheduler entity."""
#         self._hass = hass
#         self._lienage_table = LinageTable()
#         self._active_routines: dict[str, ActionEntity| None] = {}
#         self._serialization_order = OrderedQueueEntity()
#         self._wait_queues: list[ActionEntity] = []
#         self.event_listener = self.handle_event

#     @property
#     def lineage_table(self)->LinageTable:
#         """Get lienage table."""
#         return self._lienage_table


#     def attempt_locks_for_routine(self, routine: RoutineEntity)->bool:
#         """Try to acquire all locks for the routine."""

#         return all(
#             self.attempt_lock(entity_id)
#             for _, action_entity in list(routine.actions.items())[:-1]
#             for entity_id in async_get_entity_id_from_action_entity(self._hass, action_entity)
#         )

#     def acquire_locks_for_routine(self, routine: RoutineEntity)->None:
#         """Acquire all locks for the routine."""

#         for action_id, action_entity in list(routine.actions.items())[:-1]:
#             self.acquire_locks(action_entity, routine)
#             self.update_lock_state(action_entity, LOCK_STATE_ACQUIRED)
#             self.add_to_lineage_table(action_entity)

#     def release_locks_for_routine(self, routine: RoutineEntity)->None:
#         """Release all locks for the routine"""
#         self.update_lock_states_for_routine(routine, LOCK_STATE_RELEASED)

#         for action_id, action_entity in list(routine.actions.items())[:-1]:
#             target_entities = async_get_entity_id_from_action_entity(self._hass, action_entity)

#             for entity, action_entity in list(routine.actions.items())[:-1]:
#                 entity_id = async_get_entity_id_from_number(self._hass, action_entity.action[CONF_ENTITY_ID])
#                 self.release_lock(entity_id)

#                 while not self.lineage_table.ready_queues[entity_id] and self.lineage_table.ready_queues[entity_id][0].routine_id is routine.routine_id:
#                     self.lineage_table.ready_queues[entity_id].pop(0)

#     def update_lock_states_for_routine(self, routine: RoutineEntity, new_state: str)->None:
#         """Update lock states for routine."""
#         for action_id, action_entity in list(routine.actions.items())[:-1]:
#             self.update_lock_state(action_entity, new_state)

#     def attempt_lock(self, entity_id: str)->bool:
#         """Try to acquire the lock of entity_id"""
#         return self._lienage_table.locks[entity_id] is None

#     def release_lock(self, entity_id: str)->None:
#         """Release lock."""
#         self._lienage_table.locks[entity_id] = None

#     def acquire_locks(self, action_entity: ActionEntity, routine_entity: RoutineEntity)->None:
#         """Acquire lock for action entity."""

#         target_entities = async_get_entity_id_from_action_entity(self._hass, action_entity)

#         for entity in target_entities:
#             entity_id = async_get_entity_id_from_number(self._hass, entity)

#             if self._lienage_table.locks[entity_id] is None:
#                 self._lienage_table.locks[entity_id]= routine_entity
#             elif self._lienage_table.locks[entity_id] is not None and self._lienage_table.locks[entity_id].routine_id != routine_entity.routine_id:
#                 _LOGGER.error("Fail to acquire lock.")

#     def add_to_lineage_table(self, action_entity: ActionEntity)->None:
#         """Add action_entity to ready queue."""

#         target_entities = async_get_entity_id_from_action_entity(self._hass, action_entity)

#         for entity in target_entities:
#             entity_id = async_get_entity_id_from_number(self._hass, entity)
#             self._lienage_table.ready_queues[entity_id].append(action_entity)


#     def update_lock_state(self, action_entity: ActionEntity, new_lock_state: str)->None:
#         """Update lock state to new_lock_state."""
#         action_entity.lock_state = new_lock_state


#     def start_routine(self, routine_entity: RoutineEntity)->None:
#         """Start routine entity."""

#         self._serialization_order[routine_entity.routine_id] = routine_entity
#         for _, action_entity in routine_entity.actions.items():
#             if action_entity.action_id is None: # skip the virtual node
#                 continue

#             # if the entity doesn't have parents, start the action
#             if not action_entity.parents:
#                 self._start_action(action_entity)

#     def _start_action(self, action_entity: ActionEntity) -> None:
#         """Start the action."""
#         if action_entity.action_id is None:
#             _LOGGER.info("This is the end of the routine.")
#             self.release_locks_for_routine(self._serialization_order[action_entity.routine_id])
#             if self._wait_queues:
#                 self._schedule_next_routine()
#             return

#         target_entities = async_get_entity_id_from_action_entity(self._hass, action_entity)

#         for entity in target_entities:
#             entity_id = async_get_entity_id_from_number(self._hass, entity)
#             self._active_routines[entity_id] = action_entity

#         self._hass.async_create_task(action_entity.attach_triggered(log_exceptions=False))


#     # Listener to handle fired events
#     async def handle_event(self, event: Event) -> None:
#         """Handle event.

#         """
#         event_type = event.data.get(CONF_TYPE)
#         entity_id = event.data.get(CONF_ENTITY_ID)

#         action_entity = self._active_routines[str(entity_id)]


#         if action_entity is not None:
#             if event_type == RASC_COMPLETE:
#                 if action_entity.delay is not None:
#                     await action_entity.async_delay_step()

#                 self._set_active_routine(entity_id, None)

#                 self.update_action_state(action_entity, RASC_COMPLETE)

#                 # self.output_active_routines()
#                 if action_entity.children[0].action_id is not None:
#                     self._run_next_action(action_entity)
#                 else:
#                     _LOGGER.info("This is the end of the routine.")
#                     self.release_locks_for_routine(self._serialization_order[action_entity.routine_id])
#                     if self._wait_queues:
#                         self._schedule_next_routine()

#             elif event_type == RASC_START:
#                 self.update_action_state(action_entity, RASC_START)
#                 #self.output_active_routines()

#     def update_action_state(
#         self, action_entity: ActionEntity | None, new_state: str
#     ) -> None:
#         """Update action state to new state."""
#         if action_entity is None:
#             return

#         if action_entity.group:
#             active_routines = self.active_routines
#             target_entities = async_get_entity_id_from_action_entity(self._hass, action_entity)

#             for entity in target_entities:
#                 entity_id = async_get_entity_id_from_number(self._hass, entity)
#                 if active_routines[entity_id] is not None:
#                     if active_routines[entity_id].action_id is not action_entity.action_id:
#                         _LOGGER.error("Active routine doesn't have the right action_entity")

#                     return

#         else:
#             action_entity.action_state = new_state


#     # continue to do, need to check condition variable
#     def condition_check(self, action_entity: ActionEntity) -> bool:
#         """Condition check."""
#         for parent in action_entity.parents:
#             if parent.action_state != RASC_COMPLETE:
#                 return False

#         return True

#     def _set_active_routine(
#         self, entity_id: str, action_entity: ActionEntity | None
#     ) -> None:
#         """Set the action_entity as active routine."""
#         self._active_routines[entity_id] = action_entity


#     def _run_next_action(self, action_entity: ActionEntity) -> None:
#         """Run the next action for action_entity"""
#         for child in action_entity.children:
#             if self.condition_check(child):
#                 self._start_action(child)

#         # self.output_ready_queues()


#     def _schedule_next_routine(self)->None:
#         """Schedule the next routine based on FIFO."""
#         routine_entity = self._wait_queues

#         if self._wait_queues:
#             routine_entity = self._wait_queues[0]
#             if self.attempt_locks_for_routine(routine_entity):
#                 self._wait_queues.pop(0)
#                 self.acquire_locks_for_routine(routine_entity)
#                 self.start_routine(routine_entity)


class RascalSchedulerEntity:
    """Base dalss."""

    def __init__(self) -> None:
        """Init."""
        self.name = "rascal scheduler"
