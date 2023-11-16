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


SCHEDULED_STATE = "scheduled"
READY_STATE = "ready"
ACTIVE_STATE = "active"
COMPLETED_STATE = "completed"


RASC_START = "start"
RASC_COMPLETE = "complete"
RASC_RESPONSE = "rasc_response"


def setup_rascal_scheduler_entity(hass: HomeAssistant) -> None:
    """Set up RASC scheduler entity."""
    LOGGER.info("Setup rascal entity")
    hass.data[DOMAIN] = RascalSchedulerEntity(hass)
    # hass.bus.async_listen(RASC_RESPONSE, hass.data[DOMAIN].event_listener)


# async def setup_rascal_listener(hass: HomeAssistant) -> None:
#     """Setup listener."""
#     # hass.data[DOMAIN]
#     # Listen for when example_component_my_cool_event is fired


def create_x_ready_queue(hass: HomeAssistant, entity_id: str) -> None:
    """Create queue for x entity."""
    LOGGER.info("Create ready queue: %s", entity_id)
    rascal_scheduler = hass.data[DOMAIN]
    rascal_scheduler.ready_queues[entity_id] = QueueEntity({})
    rascal_scheduler.active_routines[entity_id] = None


# def delete_x_active_queue(hass: HomeAssistant, entity_id: str) -> None:
#     """Delete x entity queue."""
#     try:
#         rascal_scheduler = hass.data[DOMAIN]
#         active_routines = rascal_scheduler.get_active_routines()
#         del active_routines[entity_id]
#     except (KeyError, ValueError):
#         LOGGER.warning("Unable to delete unknown queue %s", entity_id)


def add_scheduled_routine(hass: HomeAssistant, routine: RoutineEntity) -> None:
    """Add routine to scheduled_routines."""
    rascal_scheduler = hass.data[DOMAIN]
    rascal_scheduler.set_scheduled_routine(routine)


def add_ready_routines(hass: HomeAssistant, action_entity: ActionEntity) -> None:
    """Add action_entity to ready queues."""
    rascal_scheduler = hass.data[DOMAIN]
    rascal_scheduler.set_ready_routines(
        action_entity.action[CONFIG_ENTITY_ID], action_entity
    )


def add_ready_subroutines(hass: HomeAssistant, action_entity: ActionEntity) -> None:
    """Add subroutines/next actions of action_entity to ready queues."""
    rascal_scheduler = hass.data[DOMAIN]
    rascal_scheduler.set_ready_subroutines(
        action_entity.action[CONFIG_ENTITY_ID], action_entity
    )


def get_action_entity(
    hass: HomeAssistant, routine_id: str, action_id: str
) -> ActionEntity:
    """Get action entity."""
    rascal_scheduler = hass.data[DOMAIN]
    return rascal_scheduler.get_action_entity(routine_id, action_id)


def get_action_state(hass: HomeAssistant, routine_id: str, action_id: str) -> str:
    """Get action state."""
    rascal_scheduler = hass.data[DOMAIN]
    return rascal_scheduler.get_action_state(routine_id, action_id)


def update_action_state(
    hass: HomeAssistant, routine_id: str, action_id: str, new_state: str
) -> None:
    """Update action state."""
    rascal_scheduler = hass.data[DOMAIN]
    rascal_scheduler.update_action_state(routine_id, action_id, new_state)


def dag_opeator(
    hass: HomeAssistant,
    routine_id: str,
    action_script: Sequence[dict[str, Any]],
    variables: dict[str, Any],
    context: Context | None,
):
    """Dag operator."""
    entities = {}
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
        parent = routine_id + str(step - 1) if step != 0 else None
        if parent is not None:
            entity.parent.append(parent)
        # else:
        #     entity.parent = None

        child = routine_id + str(step + 1) if step != len(action_script) - 1 else None
        if child is not None:
            entity.children.append(child)
        # else:
        #     entity.children = None

        entity.variables = variables
        entity.context = context
        entities[action_id] = entity

    return routine_id + "0", RoutineEntity(routine_id, entities)


class BaseScheduledRoutines:
    """Base class for scheduled routines."""

    _scheduled_routines: dict[str, RoutineEntity]

    @property
    def scheduled_routines(self) -> dict[str, RoutineEntity]:
        """Get scheduled routines."""
        return self._scheduled_routines


class BaseActiveRoutines:
    """Base class for active routines."""

    _active_routines: dict[str, ActionEntity]

    @property
    def active_routines(self) -> dict[str, ActionEntity]:
        """Get active routines."""
        return self._active_routines


class BaseReadyQueues:
    """Base class for ready queue."""

    _ready_queues: dict[str, QueueEntity]

    @property
    def ready_queues(self) -> dict[str, QueueEntity]:
        """Get ready routines."""
        return self._ready_queues

    def empty(self, entity_id) -> int:
        """Return if the queue is empty or not."""
        return len(self._ready_queues[entity_id])


class RascalSchedulerEntity(BaseActiveRoutines, BaseReadyQueues, BaseScheduledRoutines):
    """Representation of a rascal scehduler entity."""

    def __init__(self, hass):
        """Initialize rascal scheduler entity."""
        self.hass = hass
        self._scheduled_routines: dict[str, RoutineEntity] = {}
        self._ready_queues: Queue() = {}
        self._active_routines: dict[str, ActionEntity] = {}
        self.event_listener = self.handle_event

    # Listener to handle fired events
    def handle_event(self, event):
        """Handle event."""
        if event.data.get("type") == RASC_COMPLETE:
            entity_id = event.data.get("entity_id")
            # print("receive complete: ", entity_id)
            action_entity = self._get_active_routine(entity_id)
            self.async_run_next(action_entity)

    def async_run_next(self, action_entity: ActionEntity) -> None:
        """Handle the removal or update of a device."""
        if action_entity.children is None:
            return

        self.set_ready_subroutines(
            action_entity.action[CONFIG_ENTITY_ID], action_entity
        )
        self.set_active_routine(action_entity.action[CONFIG_ENTITY_ID], None)
        self._async_schedule_next(action_entity)

    def _async_schedule_next(self, action_entity: ActionEntity) -> None:
        """Execute fifo."""
        entity_id = action_entity.action[CONFIG_ENTITY_ID]

        if self._ready_queues.empty(entity_id) is not None:
            next_action_entity = self._ready_queues[entity_id].pop(0)
            # print("next_action_entity: ", next_action_entity.action)
            self.set_active_routine(entity_id, next_action_entity)

    def get_action_entity(self, routine_id: str, action_id: str) -> ActionEntity:
        """Get action entity."""
        return self._scheduled_routines[routine_id].actions[action_id]

    def get_action_state(self, routine_id: str, action_id: str) -> str:
        """Get action state."""
        return self._scheduled_routines[routine_id].actions[action_id].action_state

    def get_active_routine(self, entity_id: str) -> ActionEntity:
        """Get active routine."""
        return self._active_routines[entity_id]

    def set_scheduled_routine(self, routine: RoutineEntity) -> None:
        """Set scheduled routine."""
        self._scheduled_routines[routine.routine_id] = routine

    def set_ready_routines(self, entity_id: str, action_entity: ActionEntity) -> None:
        """Set ready routines."""
        entity_id = action_entity.action[CONFIG_ENTITY_ID]
        if self._active_routines[entity_id] is None:
            self.set_active_routine(entity_id, action_entity)
        else:
            self._ready_queues[entity_id].append(action_entity)
            self.update_action_state(
                action_entity.routine_id, action_entity.action_id, READY_STATE
            )

    def set_ready_subroutines(
        self, entity_id: str, action_entity: ActionEntity
    ) -> None:
        """Set ready subroutines/next actions of the action_entity."""
        ready_action_ids = action_entity.children

        for ids in ready_action_ids:
            action_entity = self.get_action_entity(action_entity.routine_id, ids)
            entity_id = action_entity.action[CONFIG_ENTITY_ID]
            if self._active_routines[entity_id] is None:
                self.set_active_routine(entity_id, action_entity)
            else:
                self._ready_queues[entity_id].append(action_entity)
                self.update_action_state(
                    action_entity.routine_id, action_entity.action_id, READY_STATE
                )

    def set_active_routine(
        self, entity_id: str, action_entity: ActionEntity | None
    ) -> None:
        """Set active routine."""
        if action_entity is not None:
            self._active_routines[entity_id] = action_entity
            self.update_action_state(
                action_entity.routine_id, action_entity.action_id, ACTIVE_STATE
            )
            thread = threading.Thread(target=self.run, args=[action_entity])
            thread.start()
            # thread.join()
            # self.async_run_next(action_entity)
        # else:
        #     self._active_routines[entity_id] = action_entity
        #     # self._active_routines[entity_id] = None #remember to change this

    def update_action_state(
        self, routine_id: str, action_id: str, new_state: str
    ) -> None:
        """Update action state to new state."""
        self._scheduled_routines[routine_id].actions[action_id].action_state = new_state

    def run(self, action_entity: ActionEntity) -> None:
        """Run action."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(action_entity.attach_triggered())
        loop.close()
