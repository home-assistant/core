"""Support for rasc."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
import threading
from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.rascalscheduler import (
    ActionEntity,
    Queue,
    QueueEntity,
    RoutineEntity,
)

from .const import DOMAIN, LOGGER

CONFIG_ACTION_ID = "action_id"
CONFIG_ENTITY_ID = "entity_id"
CONFIG_ACTION_ENTITY = "action_entity"


RASC_SCHEDULED = "scheduled"
RASC_START = "start"
RASC_COMPLETE = "complete"
RASC_RESPONSE = "rasc_response"


def setup_rascal_scheduler_entity(hass: HomeAssistant) -> None:
    """Set up RASC scheduler entity."""
    LOGGER.info("Setup rascal entity")
    hass.data[DOMAIN] = RascalSchedulerEntity(hass)
    hass.bus.async_listen(RASC_RESPONSE, hass.data[DOMAIN].event_listener)


# async def setup_rascal_listener(hass: HomeAssistant) -> None:
#     """Setup listener."""
#     # hass.data[DOMAIN]
#     # Listen for when example_component_my_cool_event is fired


def create_x_ready_queue(hass: HomeAssistant, entity_id: str) -> None:
    """Create queue for x entity."""
    LOGGER.info("Create ready queue: %s", entity_id)
    scheduler = hass.data[DOMAIN]
    scheduler.ready_queues[entity_id] = QueueEntity(None)
    scheduler.active_routines[entity_id] = None


# def delete_x_active_queue(hass: HomeAssistant, entity_id: str) -> None:
#     """Delete x entity queue."""
#     try:
#         rascal_scheduler = hass.data[DOMAIN]
#         active_routines = rascal_scheduler.get_active_routines()
#         del active_routines[entity_id]
#     except (KeyError, ValueError):
#         LOGGER.warning("Unable to delete unknown queue %s", entity_id)


# def add_scheduled_routine(hass: HomeAssistant, routine: RoutineEntity) -> None:
#     """Add routine to scheduled_routines."""
#     rascal_scheduler = hass.data[DOMAIN]
#     rascal_scheduler.set_scheduled_routine(routine)


def rascal_scheduler(hass: HomeAssistant) -> RascalSchedulerEntity:
    """Ger rascal scheduler."""
    return hass.data[DOMAIN]


def add_ready_routines(hass: HomeAssistant, action_entity: ActionEntity) -> None:
    """Add action_entity to ready queues."""
    scheduler = hass.data[DOMAIN]
    scheduler.set_ready_routines(action_entity.action[CONFIG_ENTITY_ID], action_entity)


def add_ready_subroutines(hass: HomeAssistant, action_entity: ActionEntity) -> None:
    """Add subroutines/next actions of action_entity to ready queues."""
    scheduler = hass.data[DOMAIN]
    scheduler.set_ready_subroutines(
        action_entity.action[CONFIG_ENTITY_ID], action_entity
    )


def get_action_entity(
    hass: HomeAssistant, routine_id: str, action_id: str
) -> ActionEntity:
    """Get action entity."""
    scheduler = hass.data[DOMAIN]
    return scheduler.get_action_entity(routine_id, action_id)


def get_action_state(hass: HomeAssistant, routine_id: str, action_id: str) -> str:
    """Get action state."""
    scheduler = hass.data[DOMAIN]
    return scheduler.get_action_state(routine_id, action_id)


def update_action_state(
    hass: HomeAssistant, routine_id: str, action_id: str, new_state: str
) -> None:
    """Update action state."""
    scheduler = hass.data[DOMAIN]
    scheduler.update_action_state(routine_id, action_id, new_state)


def dag_opeator(
    hass: HomeAssistant,
    routine_id: str | None,
    action_script: Sequence[dict[str, Any]],
    variables: dict[str, Any],
    context: Context | None,
):
    """Dag operator."""
    entities = {}

    if routine_id is None:
        return

    for step, action in enumerate(action_script):
        action_id = routine_id + str(step)
        entity = ActionEntity(
            hass=hass,
            action=action,
            action_id=action_id,
            action_state=None,
            routine_id=routine_id,
            variables=variables,
            context=context,
        )

        entity.variables = variables
        entity.context = context
        entities[action_id] = entity

    for step, _ in enumerate(entities):
        if step != 0:
            entities[routine_id + str(step)].parents.append(
                entities[routine_id + str(step - 1)]
            )

        if step != len(action_script) - 1:
            entities[routine_id + str(step)].children.append(
                entities[routine_id + str(step + 1)]
            )

    return routine_id + "0", RoutineEntity(routine_id, entities)


class BaseActiveRoutines:
    """Base class for active routines."""

    _active_routines: dict[str, ActionEntity]

    @property
    def active_routines(self) -> dict[str, ActionEntity]:
        """Get active routines."""
        return self._active_routines

    def get_active_routine(self, entity_id: str) -> ActionEntity:
        """Get active routine of entity_id."""
        return self._active_routines[entity_id]

    def print_active_routines(self) -> None:
        """Print the content of active routines."""
        print("\n-------------- Active Routines --------------")  # noqa: T201
        for entity_id in self._active_routines:
            print("entity_id: ", entity_id)  # noqa: T201
            if self._active_routines[entity_id] is None:
                print("None")  # noqa: T201
            else:
                print(  # noqa: T201
                    self._active_routines[entity_id].action_id,
                    self._active_routines[entity_id].action_state,
                )


class BaseReadyQueues:
    """Base class for ready queue."""

    _ready_queues: dict[str, QueueEntity]

    @property
    def ready_queues(self) -> dict[str, QueueEntity]:
        """Get ready routines."""
        return self._ready_queues

    def empty(self, entity_id) -> bool:
        """Return if the queue is empty or not."""
        return len(self._ready_queues[entity_id]) == 0

    def print_ready_queues(self) -> None:
        """Print the content of ready routines."""
        print("\n-------------- Ready Routines --------------")  # noqa: T201
        for entity_id, actions in self._ready_queues.items():
            print("entity_id:", entity_id)  # noqa: T201
            itr = iter(actions)
            for _i in range(0, len(actions)):
                action = next(itr)
                print(action.action_id, action.action_state)  # noqa: T201


class RascalSchedulerEntity(BaseActiveRoutines, BaseReadyQueues):
    """Representation of a rascal scehduler entity."""

    def __init__(self, hass):
        """Initialize rascal scheduler entity."""
        self.hass = hass
        self._ready_queues: Queue() = {}
        self._active_routines: dict[str, ActionEntity | None] = {}
        self.event_listener = self.handle_event

    # Listener to handle fired events
    async def handle_event(self, event):
        """Handle event."""
        eventType = event.data.get("type")
        entityID = event.data.get("entity_id")
        action_entity = self.get_active_routine(entityID)

        if eventType == RASC_COMPLETE:
            self.update_action_state(action_entity, RASC_COMPLETE)
            # self.print_active_routines()
            await self.async_schedule_next(action_entity)

        elif eventType == RASC_START:
            self.update_action_state(action_entity, RASC_START)
            # self.print_active_routines()

    async def async_schedule_next(self, action_entity: ActionEntity) -> None:
        """Schedule subroutines."""
        entity_id = action_entity.action[CONFIG_ENTITY_ID]

        self._schedule_subroutines(action_entity)
        self._set_active_routine(entity_id, None)
        await self._async_run_next(entity_id)

    def _schedule_subroutines(self, action_entity: ActionEntity) -> None:
        """Schedule subroutines."""
        if not action_entity.children:
            return

        self._set_ready_subroutines(action_entity)
        # self.print_ready_queues()

    async def _async_run_next(self, entity_id: str) -> None:
        """Execute FIFO."""
        if not self._ready_queues[entity_id].empty():
            next_action_entity = self._ready_queues[entity_id].pop(0)
            self._set_active_routine(entity_id, next_action_entity)

    def start_routine(self, routine_entity: RoutineEntity) -> None:
        """Start routine entity."""

        for _action_id, action_entity in routine_entity.actions.items():
            if not action_entity.parents:
                self._set_ready_routines(action_entity)

    def _set_ready_routines(self, action_entity: ActionEntity) -> None:
        """Set ready routines."""
        entity_id = action_entity.action[CONFIG_ENTITY_ID]
        if self._active_routines[entity_id] is None:
            self._set_active_routine(entity_id, action_entity)
        # else:
        #     self._ready_queues[entity_id].append(action_entity)
        #     self.update_action_state(
        #         action_entity.routine_id, action_entity.action_id, READY_STATE
        #     )

    def _set_ready_subroutines(self, action_entity: ActionEntity) -> None:
        """Set ready subroutines."""
        ready_actions = action_entity.children

        for action in ready_actions:
            entity_id = action.action[CONFIG_ENTITY_ID]

            if self._active_routines[entity_id] is None:
                self._set_active_routine(entity_id, action)
            else:
                self._ready_queues[entity_id].append(action)

    def _set_active_routine(
        self, entity_id: str, action_entity: ActionEntity | None
    ) -> None:
        """Set active routine."""
        self._active_routines[entity_id] = action_entity

        if action_entity is not None:
            self._active_routines[entity_id] = action_entity
            thread = threading.Thread(target=self.run, args=[action_entity])
            thread.start()

    def update_action_state(self, action_entity: ActionEntity, new_state: str) -> None:
        """Update action state to new state."""
        action_entity.action_state = new_state

    def run(self, action_entity: ActionEntity) -> None:
        """Run action."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(action_entity.attach_triggered())
        loop.close()
