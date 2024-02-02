"""Helpers to execute rasc entities."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator, MutableMapping, MutableSequence, Sequence
from contextlib import suppress
import copy
from datetime import timedelta
import json
import logging
import re
import threading
import time
from typing import TYPE_CHECKING, Any, TypeVar

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components.device_automation import action as device_action
from homeassistant.const import (
    CONF_CONTINUE_ON_ERROR,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    CONF_PARALLEL,
    CONF_RESPONSE_VARIABLE,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_TARGET,
    CONF_TYPE,
    DOMAIN_AUTOMATION,
    DOMAIN_PERSON,
    DOMAIN_RASCALSCHEDULER,
    DOMAIN_SCRIPT,
    DOMAIN_TTS,
    DOMAIN_ZONE,
    EVENT_CALL_SERVICE,
    NAME_SUN_NEXT_DAWN,
    NAME_SUN_NEXT_DUSK,
    NAME_SUN_NEXT_MIDNIGHT,
    NAME_SUN_NEXT_NOON,
    NAME_SUN_NEXT_RISING,
    NAME_SUN_NEXT_SETTING,
    RASC_ACK,
    RASC_COMPLETE,
    RASC_RESPONSE,
    RASC_SCHEDULED,
    RASC_START,
)
from homeassistant.core import Context, Event, HomeAssistant
from homeassistant.util import slugify

from . import config_validation as cv, entity_registry as er, service

if TYPE_CHECKING:
    from homeassistant.components.script import BaseScriptEntity

    from .entity_component import EntityComponent
from .template import device_entities

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")

_LOGGER = logging.getLogger(__name__)
_LOG_EXCEPTION = logging.ERROR + 1

CONF_ROUTINE_ID = "routine_id"
CONF_STEP = "step"
CONF_HASS = "hass"
CONF_ENTITY_REGISTRY = "entity_registry"
CONF_LOGGER = "logger"
CONF_END_VIRTUAL_NODE = "end_virtual_node"


TIMEOUT = 3000  # millisecond


def get_rascal_scheduler(hass: HomeAssistant) -> RascalSchedulerEntity:
    """Get rascal scheduler."""
    if DOMAIN_RASCALSCHEDULER not in hass.data:
        hass.data[DOMAIN_RASCALSCHEDULER] = RascalSchedulerEntity(hass)
    component: RascalSchedulerEntity = hass.data[DOMAIN_RASCALSCHEDULER]
    return component


def dag_operator(
    hass: HomeAssistant,
    name: str | None,
    routine_id: str | None,
    action_script: Sequence[dict[str, Any]],
) -> RoutineEntity:
    """Convert the script to the DAG."""
    next_parents: list[ActionEntity] = []
    entities: dict[str, ActionEntity] = {}
    config: dict[str, Any] = {}

    # configuration for each node
    config[CONF_STEP] = -1
    config[CONF_ROUTINE_ID] = routine_id
    config[CONF_HASS] = hass
    config[CONF_LOGGER] = _LOGGER

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
            action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

            entities[action_id] = ActionEntity(
                hass=hass,
                action=script,
                action_id=action_id,
                action_state=None,
                routine_id=config[CONF_ROUTINE_ID],
                delay=None,
                logger=config[CONF_LOGGER],
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
    entities["end_virtual_node"] = ActionEntity(
        hass=hass,
        action={},
        action_id=None,
        action_state=None,
        routine_id=config[CONF_ROUTINE_ID],
        delay=None,
        logger=config[CONF_LOGGER],
    )

    for parent in next_parents:
        parent.children.append(entities["end_virtual_node"])
        entities["end_virtual_node"].parents.append(parent)

    return RoutineEntity(name, routine_id, entities, TIMEOUT, _LOGGER)


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
        domain = script["service"].split(".")[0]
        if domain == DOMAIN_SCRIPT:
            script_component: EntityComponent[BaseScriptEntity] = config[
                CONF_HASS
            ].data[DOMAIN_SCRIPT]

            if script_component is not None:
                base_script = script_component.get_entity(list(script.values())[0])
                if base_script is not None and base_script.raw_config is not None:
                    next_parents = parents
                    for item in base_script.raw_config[CONF_SEQUENCE]:
                        leaf_entities = dfs(hass, item, config, next_parents, entities)
                        next_parents = leaf_entities
        else:  # only support for one target, todo
            target_entities: list[str] = []
            if CONF_DEVICE_ID in script[CONF_TARGET]:
                device_ids = []
                if isinstance(script[CONF_TARGET][CONF_DEVICE_ID], str):
                    device_ids = [script[CONF_TARGET][CONF_DEVICE_ID]]
                else:
                    device_ids = script[CONF_TARGET][CONF_DEVICE_ID]
                target_entities += [
                    entity
                    for device_id in device_ids
                    for entity in device_entities(hass, device_id)
                ]

            if CONF_ENTITY_ID in script[CONF_TARGET]:
                if isinstance(script[CONF_TARGET][CONF_ENTITY_ID], str):
                    target_entities += [script[CONF_TARGET][CONF_ENTITY_ID]]
                else:
                    target_entities += script[CONF_TARGET][CONF_ENTITY_ID]

            for target_entity in target_entities:
                config[CONF_STEP] = config[CONF_STEP] + 1
                action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

                entity_script = copy.deepcopy(script)
                entity_script[CONF_TARGET][CONF_ENTITY_ID] = [target_entity]

                entities[action_id] = ActionEntity(
                    hass=config[CONF_HASS],
                    action=entity_script,
                    action_id=action_id,
                    action_state=None,
                    routine_id=config[CONF_ROUTINE_ID],
                    delay=None,
                    logger=config[CONF_LOGGER],
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
        action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

        entities[action_id] = ActionEntity(
            hass=config[CONF_HASS],
            action=script,
            action_id=action_id,
            action_state=None,
            routine_id=config[CONF_ROUTINE_ID],
            delay=None,
            logger=config[CONF_LOGGER],
        )

        for entity in parents:
            entities[action_id].parents.append(entity)

        for entity in parents:
            entity.children.append(entities[action_id])

        next_parents.append(entities[action_id])

    return next_parents


class BaseActiveRoutines:
    """Base class for active routines."""

    _active_routines: dict[str, ActionEntity | None]
    _loops: dict[str, asyncio.AbstractEventLoop]

    @property
    def active_routines(self) -> dict[str, ActionEntity | None]:
        """Get active routines."""
        return self._active_routines

    def get_active_routine(self, entity_id: str) -> ActionEntity | None:
        """Get active routine of entity_id."""
        return self._active_routines[entity_id]

    @property
    def loops(self) -> dict[str, asyncio.AbstractEventLoop]:
        """Get loops."""
        return self._loops

    def get_loop(self, entity_id: str) -> asyncio.AbstractEventLoop:
        """Get loop of entity_id."""
        return self._loops[entity_id]

    def create_bg_loop(self) -> asyncio.AbstractEventLoop:
        """Create event loop in background."""

        def to_bg(loop: asyncio.AbstractEventLoop) -> None:
            """Create event loop in background."""
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            except asyncio.CancelledError as e:
                _LOGGER.error("Error cancelling loop %s", e)
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.stop()
                loop.close()

        new_loop = asyncio.new_event_loop()
        t = threading.Thread(target=to_bg, args=(new_loop,))
        t.start()
        return new_loop

    def output_active_routines(self) -> None:
        """Output the content of active routines."""
        active_routines = []
        for entity_id, action_entity in self._active_routines.items():
            if action_entity is not None:
                entity_json = {
                    "entity_id": entity_id,
                    "action_id": action_entity.action_id,
                    "action_state": action_entity.action_state,
                }

            else:
                entity_json = {
                    "entity_id": entity_id,
                    "action_id": "None",
                    "action_state": "None",
                }

            active_routines.append(entity_json)

        out = {"Type": "Active Routines", "Routines": active_routines}
        print(json.dumps(out, indent=2))  # noqa: T201


class BaseReadyQueues:
    """Base class for ready queue."""

    _ready_queues: dict[str, QueueEntity]

    @property
    def ready_queues(self) -> dict[str, QueueEntity]:
        """Get ready routines."""
        return self._ready_queues

    def output_ready_queues(self) -> None:
        """Output the content of ready routines."""
        ready_routines = []
        for entity_id, actions in self._ready_queues.items():
            action_list = []
            for action in actions:
                sub_entity_json = {
                    "action_id": action.action_id,
                    "action_state": action.action_state,
                }

                action_list.append(sub_entity_json)

            entity_json = {"entity_id": entity_id, "actions": action_list}

            ready_routines.append(entity_json)

        out = {"Type": "Ready Routines", "Routines": ready_routines}
        print(json.dumps(out, indent=2))  # noqa: T201


class RascalSchedulerEntity(BaseActiveRoutines, BaseReadyQueues):
    """Representation of a rascal scehduler entity."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize rascal scheduler entity."""
        self.hass = hass
        self._ready_queues: dict[str, QueueEntity] = {}
        self._active_routines: dict[str, ActionEntity | None] = {}
        self._loops: dict[
            str, asyncio.AbstractEventLoop
        ] = {}  # loops for active_rountines
        hass.bus.async_listen(RASC_RESPONSE, self.handle_event)

    def start_routine(self, routine_entity: RoutineEntity) -> None:
        """Start routine entity."""
        for _, action_entity in routine_entity.actions.items():
            # skip virtual node
            if action_entity.action_id is None:
                continue

            # todo, switch case based on action type
            pattern = re.compile("^[^.]+[.][^.]+$")

            action = cv.determine_script_action(action_entity.action)

            # todo, convert the number to the entity id if it is needed
            if action is not EVENT_CALL_SERVICE:
                if not pattern.match(action_entity.action[CONF_ENTITY_ID]):
                    registry = self.hass.data[CONF_ENTITY_REGISTRY]
                    action_entity.action[CONF_ENTITY_ID] = registry.async_get(
                        action_entity.action[CONF_ENTITY_ID]
                    ).as_partial_dict[CONF_ENTITY_ID]

            # if CONF_TARGET in action_entity.action:
            #     if not pattern.match(action_entity.action[CONF_TARGET][CONF_ENTITY_ID][0]):
            #         registry = self.hass.data[CONF_ENTITY_REGISTRY]
            #         action_entity.action[CONF_TARGET][CONF_ENTITY_ID][0] = registry.async_get(
            #             action_entity.action[CONF_TARGET][CONF_ENTITY_ID][0]
            #         ).as_partial_dict[CONF_ENTITY_ID]

            # if the entity doesn't have parents, set it to ready queues
            if not action_entity.parents:
                self._start_action(action_entity)

    def _start_action(self, action_entity: ActionEntity) -> None:
        """Set the action entity into ready routines.

        a. if active routine is None, set the action_entity as active routine
        b. else, add the action_entity to ready queues.

        """

        # todo, remove routine from the table
        if action_entity.action_id is None:
            print("This is the end of the routine.")  # noqa: T201
            return

        # todo, get entity id based on the action_type
        if CONF_TARGET in action_entity.action:
            entity_id = action_entity.action[CONF_TARGET][CONF_ENTITY_ID][0]

        else:
            entity_id = action_entity.action[CONF_ENTITY_ID]

        if self._active_routines[entity_id] is None:  # set as active routine
            self._set_active_routine(entity_id, action_entity)
        else:  # set to ready queue
            self._ready_queues[entity_id].append(action_entity)

    def _set_active_routine(
        self, entity_id: str, action_entity: ActionEntity | None
    ) -> None:
        """Set the action_entity as active routine."""
        self._active_routines[entity_id] = action_entity

        if action_entity is not None:
            self._active_routines[entity_id] = action_entity

            # run loop in background
            bg_loop = self.get_loop(entity_id)
            asyncio.run_coroutine_threadsafe(
                self.attach_trigger(action_entity), bg_loop
            )
            # bg_loop.call_soon_threadsafe(bg_loop.stop)
            # thread = threading.Thread(target=t.run, args=[action_entity])
            # thread.start()

    # Why cannot pass async function to thread?
    # RuntimeError: Task <Task pending name='Task-738' coro=<ActionEntity.attach_triggered()
    # running at /workspaces/home-assistant-core/homeassistant/helpers/rascalscheduler.py:189>
    # cb=[_run_until_complete_cb() at /usr/local/lib/python3.11/asyncio/base_events.py:180]>
    # got Future <Task pending name='Task-739' coro=<async_refresh_after.<locals>._async_wrap()
    # running at /workspaces/home-assistant-core/homeassistant/components/tplink/entity.py:25>
    # cb=[set.remove()]> attached to a different loop

    # def run(self, action_entity: ActionEntity) -> None:
    #     """Run action entity."""
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(self.loop)
    #     loop.run_until_complete(action_entity.attach_triggered(log_exceptions=False))
    #     loop.close()

    async def attach_trigger(self, action_entity: ActionEntity) -> None:
        """Trigger action_entity."""
        await action_entity.attach_triggered(log_exceptions=False)

    # Listener to handle fired events
    async def handle_event(self, event: Event) -> None:
        """Handle event.

        a. When the event type is complete
        - change the state to RASC_COMPLETE
        - schedule the next action
        b. When the event type is start
        - change the state to RASC_START

        """

        event_type = event.data.get(CONF_TYPE)
        entity_id = event.data.get(CONF_ENTITY_ID)

        if event_type == RASC_ACK:
            return

        if entity_id is not None:
            action_entity = self.get_active_routine(str(entity_id))

        if action_entity is not None:
            if event_type == RASC_COMPLETE:
                if action_entity.delay is not None:
                    await action_entity.async_delay_step()

                self.update_action_state(action_entity, RASC_COMPLETE)
                # self.output_active_routines()
                self.schedule_next(action_entity)

        elif event_type == RASC_START:
            self.update_action_state(action_entity, RASC_START)
            # self.output_active_routines()

    def schedule_next(self, action_entity: ActionEntity | None) -> None:
        """After action_entity completed, schedule the next subroutines."""
        if action_entity is None:
            return

        action = cv.determine_script_action(action_entity.action)

        if action is EVENT_CALL_SERVICE:
            entity_id = action_entity.action[CONF_TARGET][CONF_ENTITY_ID][0]
        else:
            entity_id = action_entity.action[CONF_ENTITY_ID]

        self._add_subroutines_to_ready_queues(action_entity)

        self._set_active_routine(
            entity_id, None
        )  # remove the current action_entity from action_entity

        self._schedule_next(entity_id)

    # continue to do, need to check condition variable
    def condition_check(self, action_entity: ActionEntity) -> bool:
        """Condition check."""
        for parent in action_entity.parents:
            if parent.action_state != RASC_COMPLETE:
                return False

        return True

    def _add_subroutines_to_ready_queues(self, action_entity: ActionEntity) -> None:
        """After action_entity completed, schedule the next subroutines."""
        if not action_entity.children:
            return

        next_subroutine = action_entity.children

        for action in next_subroutine:
            if self.condition_check(action):
                self._start_action(action)

        # self.output_ready_queues()

    def _schedule_next(self, entity_id: str) -> None:
        """Schedule the next action using FIFO strategy."""
        if self._ready_queues[entity_id]:
            next_action_entity = self._ready_queues[entity_id].pop(0)
            self._set_active_routine(entity_id, next_action_entity)

    def update_action_state(
        self, action_entity: ActionEntity | None, new_state: str
    ) -> None:
        """Update action state to new state."""
        if action_entity is None:
            return

        action_entity.action_state = new_state


def create_x_ready_queue(hass: HomeAssistant, entity_id: str) -> None:
    """Create queue for x entity."""
    domains = [DOMAIN_SCRIPT, DOMAIN_AUTOMATION, DOMAIN_PERSON, DOMAIN_ZONE, DOMAIN_TTS]
    full_names = [
        NAME_SUN_NEXT_SETTING,
        NAME_SUN_NEXT_RISING,
        NAME_SUN_NEXT_DAWN,
        NAME_SUN_NEXT_DUSK,
        NAME_SUN_NEXT_MIDNIGHT,
        NAME_SUN_NEXT_NOON,
    ]

    entity = entity_id.split(".")
    domain = entity[0]
    full_name = entity[1]

    if full_name is not None:
        if domain not in domains and full_name not in full_names:
            scheduler = get_rascal_scheduler(hass)
            scheduler.ready_queues[entity_id] = QueueEntity(None)
            scheduler.active_routines[entity_id] = None
            scheduler.loops[entity_id] = scheduler.create_bg_loop()

            _LOGGER.info("Create queue: %s", entity_id)


def delete_x_active_queue(hass: HomeAssistant, entity_id: str) -> None:
    """Delete x entity queue."""
    try:
        scheduler = get_rascal_scheduler(hass)

        del scheduler.ready_queues[entity_id]
        del scheduler.active_routines[entity_id]

        scheduler.loops[entity_id].call_soon_threadsafe(scheduler.loops[entity_id].stop)
        del scheduler.loops[entity_id]

        _LOGGER.info("Delete queue: %s", entity_id)
    except (KeyError, ValueError):
        _LOGGER.error("Unable to delete unknown queue %s", entity_id)


def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises ValueError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.device_id is None:
        raise ValueError(f"Entity {entity_id} is not a valid entity.")

    return str(entity_entry.device_id)


class RoutineEntity:
    """A class that describes routine entities for Rascal Scheduler."""

    def __init__(
        self,
        name: str | None,
        routine_id: str | None,
        actions: dict[str, ActionEntity],
        timeout: float,
        logger: logging.Logger | None = None,
        log_exceptions: bool = True,
    ) -> None:
        """Initialize a routine entity."""
        self.name = name
        self.routine_id = routine_id
        self.actions = actions
        self._start_time: float | None = None
        self._last_trigger_time: float | None = None
        self._timeout = timeout
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

    @property
    def start_time(self) -> float | None:
        """Return the start time of the routine entity."""
        return self._start_time

    @property
    def last_trigger_time(self) -> float | None:
        """Return the last trigger time or the routine entity."""
        return self._last_trigger_time

    @property
    def timeout(self) -> float:
        """Return the timeout of the routine entity."""
        return self._timeout

    def set_variables(self, var: dict[str, Any]) -> None:
        """Set variables to all the action entities."""
        for entity in self.actions.values():
            entity.variables = var

    def set_context(self, ctx: Context | None) -> None:
        """Set context to all the action entities."""
        for entity in self.actions.values():
            entity.context = ctx

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        """Set logger."""
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

    def duplicate(self) -> RoutineEntity:
        """Duplicate the routine entity."""

        routine_entity = {}

        for action_id, entity in self.actions.items():
            if action_id is not None:
                routine_entity[action_id] = ActionEntity(
                    hass=entity.hass,
                    action=entity.action,
                    action_id=entity.action_id,
                    action_state=None,
                    routine_id=entity.routine_id,
                    delay=entity.delay,
                    logger=entity.get_logger(),
                )

        for action_id, entity in self.actions.items():
            if action_id is not None:
                for parent in entity.parents:
                    if parent.action_id is not None:
                        routine_entity[action_id].parents.append(
                            routine_entity[parent.action_id]
                        )

                for child in entity.children:
                    if child.action_id is not None:
                        routine_entity[action_id].children.append(
                            routine_entity[child.action_id]
                        )
                    else:
                        routine_entity[action_id].children.append(
                            routine_entity["end_virtual_node"]
                        )

        if self._last_trigger_time is None:
            self._start_time = time.time()
            self._last_trigger_time = self._start_time
        else:
            self._last_trigger_time = self._start_time
            self._start_time = time.time()

        return RoutineEntity(
            self.name, self.routine_id, routine_entity, self._timeout, self._logger
        )

    def output(self) -> None:
        """Print the routine information."""
        actions = []
        for _, entity in self.actions.items():
            parents = []
            children = []

            for parent in entity.parents:
                parents.append(parent.action_id)

            for child in entity.children:
                children.append(child.action_id)

            entity_json = {
                "action_id": entity.action_id,
                "action": entity.action,
                "state": entity.action_state,
                "parents": parents,
                "children": children,
                "delay": str(entity.delay),
            }

            actions.append(entity_json)

        out = {"routine_id": self.routine_id, "actions": actions}

        print(json.dumps(out, indent=2))  # noqa: T201


class ActionEntity:
    """Initialize a routine entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        action: dict[str, Any],
        action_id: str | None,
        action_state: str | None,
        routine_id: str | None,
        delay: timedelta | None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize a routine entity."""
        self.hass = hass
        self.action = action
        self.action_id = action_id

        if action_state is None:
            self.action_state = RASC_SCHEDULED
        else:
            self.action_state = action_state

        self.parents: list[ActionEntity] = []
        self.children: list[ActionEntity] = []
        self.routine_id = routine_id
        self.delay = delay
        self.variables: dict[str, Any]
        self.context: Context | None
        self._log_exceptions = False
        self._set_logger(logger)
        self._stop = asyncio.Event()

    def get_logger(self) -> logging.Logger | None:
        """Get logger."""
        return self._logger

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        """Set logger."""
        self._logger = logger

    def _step_log(self, default_message: Any, timeout: Any = None) -> None:
        """Step log."""
        _timeout = (
            "" if timeout is None else f" (timeout: {timedelta(seconds=timeout)})"
        )
        self._log(
            "Executing step %s%s", default_message, _timeout
        )  # pylint: disable=protected-access

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        """Log."""
        msg = f"%s: {msg}"
        args = (str(self.action_id), *args)

        if self._logger is not None:
            if level == _LOG_EXCEPTION:
                self._logger.exception(msg, *args, **kwargs)
            else:
                self._logger.log(level, msg, *args, **kwargs)

    async def attach_triggered(self, log_exceptions: bool) -> None:
        """Trigger the function."""
        action = cv.determine_script_action(self.action)

        continue_on_error = self.action.get(CONF_CONTINUE_ON_ERROR, False)

        try:
            handler = f"_async_{action}_step"
            await getattr(self, handler)()

        except Exception as ex:  # pylint: disable=broad-except
            self._handle_exception(
                ex, continue_on_error, self._log_exceptions or log_exceptions
            )

    async def _async_device_step(self) -> None:
        """Execute device automation."""
        await device_action.async_call_action_from_config(
            self.hass, self.action, self.variables, self.context
        )

    async def async_delay_step(self) -> None:
        """Handle delay."""
        await self._async_delay_step()

    async def _async_delay_step(self) -> None:
        """Handle delay."""
        if self.delay is not None:
            delay = self.delay
            self._step_log(f"delay {delay}")

            try:
                async with asyncio.timeout(delay.total_seconds()):
                    await self._stop.wait()
            except asyncio.TimeoutError:
                self._step_log("delay completed")

    async def _async_call_service_step(self) -> None:
        """Call the service specified in the action."""
        self._step_log("call service")

        params = service.async_prepare_call_from_config(
            self.hass, self.action, self.variables
        )

        # Validate response data parameters. This check ignores services that do
        # not exist which will raise an appropriate error in the service call below.
        response_variable = self.action.get(CONF_RESPONSE_VARIABLE)

        return_response = response_variable is not None

        response_data = await self._async_run_long_action(
            self.hass.async_create_task(
                self.hass.services.async_call(
                    **params,
                    blocking=True,
                    context=self.context,
                    return_response=return_response,
                )
            ),
        )
        if response_variable:
            self.variables[response_variable] = response_data

    async def _async_run_long_action(self, long_task: asyncio.Task[_T]) -> _T | None:
        """Run a long task while monitoring for stop request."""

        async def async_cancel_long_task() -> None:
            # Stop long task and wait for it to finish.
            long_task.cancel()
            with suppress(Exception):
                await long_task

        # Wait for long task while monitoring for a stop request.
        stop_task = self.hass.async_create_task(self._stop.wait())
        try:
            await asyncio.wait(
                {long_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        # If our task is cancelled, then cancel long task, too. Note that if long task
        # is cancelled otherwise the CancelledError exception will not be raised to
        # here due to the call to asyncio.wait(). Rather we'll check for that below.
        except asyncio.CancelledError:
            await async_cancel_long_task()
            raise
        finally:
            stop_task.cancel()

        if long_task.cancelled():
            raise asyncio.CancelledError
        if long_task.done():
            # Propagate any exceptions that occurred.
            return long_task.result()
        # Stopped before long task completed, so cancel it.
        await async_cancel_long_task()
        return None

    def _handle_exception(
        self, exception: Exception, continue_on_error: bool, log_exceptions: bool
    ) -> None:
        if not isinstance(exception, _HaltScript) and log_exceptions:
            self._log_exception(exception)

        if not continue_on_error:
            raise exception

        # An explicit request to stop the script has been raised.
        if isinstance(exception, _StopScript):
            raise exception

        # These are incorrect scripts, and not runtime errors that need to
        # be handled and thus cannot be stopped by `continue_on_error`.
        if isinstance(
            exception,
            (
                vol.Invalid,
                exceptions.TemplateError,
                exceptions.ServiceNotFound,
                exceptions.InvalidEntityFormatError,
                exceptions.NoEntitySpecifiedError,
                exceptions.ConditionError,
            ),
        ):
            raise exception

        # Only Home Assistant errors can be ignored.
        if not isinstance(exception, exceptions.HomeAssistantError):
            raise exception

    def _log_exception(self, exception: Exception) -> None:
        """Log exception."""
        action_type = cv.determine_script_action(self.action)

        error = str(exception)

        if isinstance(exception, vol.Invalid):
            error_desc = "Invalid data"

        elif isinstance(exception, exceptions.TemplateError):
            error_desc = "Error rendering template"

        elif isinstance(exception, exceptions.Unauthorized):
            error_desc = "Unauthorized"

        elif isinstance(exception, exceptions.ServiceNotFound):
            error_desc = "Service not found"

        elif isinstance(exception, exceptions.HomeAssistantError):
            error_desc = "Error"

        else:
            error_desc = "Unexpected error"

        _LOGGER.warning(
            "Error executing script. %s for %s at action_id %s: %s",
            error_desc,
            action_type,
            self.action_id,
            error,
        )


class Queue(MutableMapping[_KT, _VT]):
    """Representation of an queue for rascal scheduler."""

    __slots__ = ("_queue",)

    _queue: dict[_KT, _VT]

    def __init__(self, queue: Any) -> None:
        """Initialize a queue entity."""
        if queue is None:
            self._queue = {}
        else:
            self._queue = queue

    def __getitem__(self, __key: _KT) -> _VT:
        """Get item."""
        return self._queue[__key]

    def __delitem__(self, __key: _KT) -> None:
        """Delete item."""
        del self._queue[__key]

    def __iter__(self) -> Iterator[_KT]:
        """Iterate items."""
        return iter(self._queue)

    def __len__(self) -> int:
        """Get the size of the queue."""
        return len(self._queue)

    def __setitem__(self, __key: _KT, __value: _VT) -> None:
        """Set item."""
        self._queue[__key] = __value


class QueueEntity(MutableSequence[_VT]):
    """Representation of an queue for rascal scheduler."""

    __slots__ = ("_queue_entities",)

    _queue_entities: list[_VT]

    def __init__(self, queue_entities: Any) -> None:
        """Initialize a queue entity."""
        if queue_entities is None:
            self._queue_entities = []
        else:
            self._queue_entities = queue_entities

    def __getitem__(self, __key: Any) -> Any:
        """Get item."""
        return self._queue_entities[__key]

    def __delitem__(self, __key: Any) -> Any:
        """Delete item."""
        self._queue_entities.pop(__key)

    def __len__(self) -> int:
        """Get the size of the queue."""
        return len(self._queue_entities)

    def __setitem__(self, __key: Any, __value: Any) -> None:
        """Set item."""
        self._queue_entities[__key] = __value

    def insert(self, __key: Any, __value: Any) -> None:
        """Insert key value pair."""
        self._queue_entities.insert(__key, __value)

    def empty(self) -> bool:
        """Return empty."""
        return len(self._queue_entities) == 0

    def append(self, __value: Any) -> None:
        """Append new value."""
        self._queue_entities.append(__value)


class _HaltScript(Exception):
    """Throw if script needs to stop executing."""


class _StopScript(_HaltScript):
    """Throw if script needs to stop."""

    def __init__(self, message: str, response: Any) -> None:
        """Initialize a halt exception."""
        super().__init__(message)
        self.response = response
