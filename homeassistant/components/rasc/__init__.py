"""The rasc integration."""
from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import time
from typing import TYPE_CHECKING, Any, TypeVar, cast

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_GROUP_ID,
    ATTR_SERVICE,
    CONF_EVENT,
    CONF_NAME,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
)
from homeassistant.core import (
    HassJobType,
    HomeAssistant,
    Service,
    ServiceCall,
    ServiceResponse,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.dynamic_polling import get_best_distribution, get_polls
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import device_entities
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, RASC_ACK, RASC_COMPLETE, RASC_RESPONSE, RASC_START

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import EntityPlatform
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


_R = TypeVar("_R")

DEFAULT_NAME = "RASCal Abstraction"
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the RASC component."""
    component = hass.data[DOMAIN] = RASC(LOGGER, DOMAIN, hass)

    await component.async_load()

    return True


class RASC(ABC):
    """RASC Component."""

    def __init__(self, logger, domain, hass: HomeAssistant) -> None:
        """Initialize an rasc entity."""
        self.states: dict[str, RASCState | None] = {}
        self.logger = logger
        self.domain = domain
        self.hass = hass
        self._store = RASCStore(self.hass)

    def _get_entity_ids(self, service_call: ServiceCall):
        entities: list[str] = []
        if ATTR_DEVICE_ID in service_call.data:
            entities += [
                entity
                for _device_id in service_call.data[ATTR_DEVICE_ID]
                for entity in device_entities(self.hass, _device_id)
            ]
        if ATTR_ENTITY_ID in service_call.data:
            if isinstance(service_call.data[ATTR_ENTITY_ID], str):
                entities += [service_call.data[ATTR_ENTITY_ID]]
            else:
                entities += service_call.data[ATTR_ENTITY_ID]
        return entities

    def _track_service(self, context: Context, service_call: ServiceCall):
        entity_ids = self._get_entity_ids(service_call)
        platforms: list[tuple[EntityPlatform, list[Entity]]] = self.hass.data[
            service_call.domain
        ].async_get_platforms(entity_ids)

        for platform, entities in platforms:
            for entity in entities:
                state = self.states[entity.entity_id] = self._get_rasc_state(
                    context, entity, service_call
                )
                if entity.should_poll:
                    next_interval = state.get_polling_interval()
                    self.hass.create_task(
                        platform.track_entity_state(entity, next_interval)
                    )

    def _get_rasc_state(
        self, context: Context, entity: Entity, service_call: ServiceCall
    ) -> RASCState:
        """Get RASC state on the given Event e."""
        params = {
            CONF_SERVICE: service_call.service,
            CONF_SERVICE_DATA: service_call.data,
        }
        start_state = (
            entity.async_get_action_target_state({CONF_EVENT: RASC_START, **params})
        ) or {}
        complete_state = (
            entity.async_get_action_target_state({CONF_EVENT: RASC_COMPLETE, **params})
        ) or {}
        return RASCState.create(
            context, entity, service_call, start_state, complete_state, self._store
        )

    def _match_state(self, state: RASCState, rules: dict[str, Any]) -> bool:
        matched = True
        if not rules:
            raise ValueError("no entry in rules.")
        for attr, match in rules.items():
            entity_attr = getattr(state.entity, attr)
            if entity_attr is None:
                LOGGER.warning(
                    "Entity %s does not have attribute %s", state.entity.entity_id, attr
                )
                continue
            if not match(entity_attr):
                matched = False
                break
        return matched

    async def _update_state(self, state: RASCState) -> bool:
        """Update RASC and fire responses if any."""

        # check complete state
        complete_state_matched = self._match_state(state, state.complete_state)
        # prevent hazardous changes
        transition = state.transition
        if complete_state_matched and (
            transition is None or time.time() - state.exec_time > transition / 2
        ):
            # fire start response if haven't
            if not state.started:
                await state.set_started()
                self._fire_by_state(RASC_START, state)

            self._fire_by_state(RASC_COMPLETE, state)
            await state.set_completed()
            time_to_complete = time.time() - state.exec_time
            self._update_store(
                state.entity,
                state.service_call.service,
                state.transition,
                time_to_complete=time_to_complete,
            )

            return True

        start_state_matched = self._match_state(state, state.start_state)
        if start_state_matched and not state.started:
            self._fire_by_state(RASC_START, state)
            await state.set_started()
            time_to_start = time.time() - state.exec_time
            state.exec_time = time.time()
            self._update_store(
                state.entity,
                state.service_call.service,
                state.transition,
                time_to_start=time_to_start,
            )
        return False

    def _update_store(
        self,
        entity: Entity,
        action: str,
        transition: float,
        time_to_start: float | None = None,
        time_to_complete: float | None = None,
    ):
        key = ",".join((entity.entity_id, action, str(transition)))
        histories = self._store.histories
        if key not in histories:
            histories[key] = RASCHistory()

        if time_to_start:
            histories[key].append_s(time_to_start)
        if time_to_complete:
            histories[key].append_c(time_to_complete)

        self.hass.loop.create_task(self._store.async_save())

    def _fire_by_state(self, rasc_type: str, state: RASCState | None = None):
        if state is None:
            entity_id = None
            action = None
            group_id = None
        else:
            entity_id = state.entity.entity_id
            action = state.service_call.service
            group_id = state.service_call.data.get(ATTR_GROUP_ID)
        self._fire(rasc_type, entity_id, action, group_id)

    def _fire(
        self,
        rasc_type: str,
        entity_id: str | None,
        action: str | None,
        group_id: str | None = None,
    ):
        LOGGER.info("%s %s: %s", entity_id, action, rasc_type)
        self.hass.bus.async_fire(
            RASC_RESPONSE,
            {
                "type": rasc_type,
                ATTR_SERVICE: action,
                ATTR_ENTITY_ID: entity_id,
                ATTR_GROUP_ID: group_id,
            },
        )

    async def async_load(self) -> None:
        """Load persistent store."""
        await self._store.async_load()

    async def async_on_push_event(self, entity: Entity) -> None:
        """Handle update event from push-based entity."""
        await self.update(entity)

    async def update(
        self,
        entity: Entity,
        platform: EntityPlatform | DataUpdateCoordinator | None = None,
    ) -> None:
        """Update rasc state."""
        rasc_state = self.states.get(entity.entity_id)
        if not rasc_state:
            return
        completed = await self._update_state(rasc_state)
        if completed:
            # TODO: add garbage collection # pylint: disable=fixme
            # del self.states[entity.entity_id]
            return
        # if the entity is push-based, no need to get polling interval
        if not entity.should_poll or platform is None:
            return

        polling_interval = rasc_state.get_polling_interval()
        await asyncio.sleep(polling_interval.total_seconds())
        await platform.track_entity_state(entity)

    def execute_service(
        self, handler: Service, service_call: ServiceCall
    ) -> tuple[
        asyncio.Task[ServiceResponse],
        asyncio.Task[ServiceResponse],
        asyncio.Task[ServiceResponse],
    ]:
        """Execute a service."""

        s_cv = asyncio.Condition()
        c_cv = asyncio.Condition()
        context = Context(s_cv, c_cv)

        async def a_future(
            context: Context, handler: Service, service_call: ServiceCall
        ) -> ServiceResponse:
            entity_ids = self._get_entity_ids(service_call)

            for entity_id in entity_ids:
                self.states[entity_id] = None  # before receiving ack

            response: ServiceResponse = None
            job = handler.job
            target = job.target
            if job.job_type == HassJobType.Coroutinefunction:
                if TYPE_CHECKING:
                    target = cast(Callable[..., Coroutine[Any, Any, _R]], target)
                response = await target(service_call)
            elif job.job_type == HassJobType.Callback:
                if TYPE_CHECKING:
                    target = cast(Callable[..., _R], target)
                response = target(service_call)
            else:
                if TYPE_CHECKING:
                    target = cast(Callable[..., _R], target)
                response = await self.hass.async_add_executor_job(target, service_call)
            for entity_id in entity_ids:
                self._fire(RASC_ACK, entity_id, service_call.service)

            # start tracking after receiving ack
            self._track_service(context, service_call)
            return response

        async def s_future(
            context: Context, service_call: ServiceCall
        ) -> ServiceResponse:
            entity_ids = self._get_entity_ids(service_call)

            def check_started() -> bool:
                for state in self.states.values():
                    if state is None or not state.started:
                        return False
                return True

            async with context.s_cv:
                await context.s_cv.wait_for(check_started)
                return entity_ids

        async def c_future(
            context: Context, service_call: ServiceCall
        ) -> ServiceResponse:
            entity_ids = self._get_entity_ids(service_call)

            def check_completed() -> bool:
                for state in self.states.values():
                    if state is None or not state.completed:
                        return False
                return True

            async with context.c_cv:
                await context.c_cv.wait_for(check_completed)
                return entity_ids

        return (
            self.hass.async_create_task(a_future(context, handler, service_call)),
            self.hass.async_create_task(s_future(context, service_call)),
            self.hass.async_create_task(c_future(context, service_call)),
        )


class StateDetector(ABC):
    """RASC State Detector."""

    def __init__(self, history: list[float] | None) -> None:
        """Init State Detector."""
        super().__init__()
        if history is None or len(history) == 0:
            self.static = True
            return
        self.static = False
        self.cur_poll = 0
        if len(history) == 1:
            self.polls = [history[0]]
            return
        dist = get_best_distribution(history)
        self.upper_bound = dist.ppf(0.99)
        self.polls = get_polls(dist, self.upper_bound)

    def next_interval(self) -> timedelta:
        """Get next interval."""
        if self.static:
            return timedelta(seconds=1)
        if self.cur_poll < len(self.polls):
            cur = self.cur_poll
            self.cur_poll += 1
            return timedelta(seconds=self.polls[cur])
        return timedelta(seconds=1)


class RASCHistory(ABC):
    """RASC History."""

    def __init__(
        self,
        st_history: list[float] | None = None,
        ct_history: list[float] | None = None,
    ) -> None:
        """Init History."""
        self.st_history = st_history or []
        self.ct_history = ct_history or []

    def append_s(self, start_time: float) -> None:
        """Append start time to history."""
        self.st_history.append(start_time)

    def append_c(self, complete_time: float) -> None:
        """Append complete time to history."""
        self.ct_history.append(complete_time)


class RASCState(ABC):
    """RASC State."""

    def __init__(
        self,
        context: Context,
        entity: Entity,
        service_call: ServiceCall,
        start_state: dict[str, Any],
        complete_state: dict[str, Any],
        transition: float,
        history: RASCHistory,
    ) -> None:
        """Init rasc state."""
        self.start_state = start_state
        self.complete_state = complete_state
        self.transition = transition
        self.service_call = service_call
        self.entity = entity
        self._attr_started = False
        self._attr_completed = False
        self._context = context
        self._next_response = RASC_START
        if entity.should_poll:
            self.s_detector = StateDetector(history.st_history)
            self.c_detector = StateDetector(history.ct_history)
        # metadata
        self.exec_time = time.time()

    @classmethod
    def create(
        cls,
        context: Context,
        entity: Entity,
        service_call: ServiceCall,
        start_state: dict[str, Any],
        complete_state: dict[str, Any],
        store: RASCStore,
    ) -> RASCState:
        """Create rasc state."""
        transition: float = service_call.data.get("transition", 0)
        key = ",".join((entity.entity_id, service_call.service, str(transition)))
        history = store.histories[key]
        return RASCState(
            context,
            entity,
            service_call,
            start_state,
            complete_state,
            transition,
            history,
        )

    @property
    def started(self) -> bool:
        """Return if the action has started."""
        return self._attr_started

    @property
    def completed(self) -> bool:
        """Return if the action has completed."""
        return self._attr_completed

    def get_polling_interval(self) -> timedelta:
        """Get polling interval."""
        if self._next_response == RASC_START:
            return self.s_detector.next_interval()
        if self._next_response == RASC_COMPLETE:
            return self.c_detector.next_interval()
        return timedelta(seconds=1)

    async def set_started(self):
        """Set started."""
        self._attr_started = True
        self._next_response = RASC_COMPLETE
        async with self._context.s_cv:
            self._context.s_cv.notify()

    async def set_completed(self):
        """Set completed."""
        self._attr_completed = True
        self._next_response = None
        async with self._context.c_cv:
            self._context.c_cv.notify()


class RASCStore(ABC):
    """RASC perminent store."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new config object."""
        self.hass = hass

        self._store = self._ConfigStore(hass)
        self.histories: dict[str, RASCHistory] = {}
        self._init_lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load stored data."""
        async with self._init_lock:
            if (data := await self._store.async_load()) is None:
                data = cast(dict[str, dict[str, list[float]]], {})

            self.histories = {key: RASCHistory(**hist) for key, hist in data.items()}

    async def async_save(self) -> None:
        """Store data."""
        await self._store.async_save(
            {
                key: {
                    "st_history": hist.st_history,
                    "ct_history": hist.ct_history,
                }
                for key, hist in self.histories.items()
            }
        )

    class _ConfigStore(Store[dict[str, dict[str, list[float]]]]):
        def __init__(self, hass: HomeAssistant) -> None:
            """Initialize storage class."""
            super().__init__(
                hass,
                1,
                "rasc.history",
                private=True,
                atomic_writes=True,
            )


class Context:
    """RASC Context."""

    def __init__(self, s_cv: asyncio.Condition, c_cv: asyncio.Condition) -> None:
        """Initialize context."""
        self.s_cv = s_cv
        self.c_cv = c_cv
