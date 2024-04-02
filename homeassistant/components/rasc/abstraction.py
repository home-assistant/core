"""The rasc integration."""
from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Callable, Coroutine
import datetime
from datetime import timedelta
import json
import time
from typing import TYPE_CHECKING, Any, TypeVar, cast

from homeassistant.components import notify
from homeassistant.const import (
    ATTR_ACTION_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_GROUP_ID,
    ATTR_SERVICE,
    CONF_EVENT,
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
from homeassistant.helpers.dynamic_polling import get_best_distribution, get_polls
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.template import device_entities
from homeassistant.helpers.typing import StateType
import homeassistant.util.dt as dt_util

from .const import LOGGER, RASC_ACK, RASC_COMPLETE, RASC_RESPONSE, RASC_START

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import EntityPlatform
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


_R = TypeVar("_R")


class RASC(ABC):
    """RASC Component."""

    def __init__(self, logger, domain, hass: HomeAssistant) -> None:
        """Initialize an rasc entity."""
        self.logger = logger
        self.domain = domain
        self.hass = hass
        self._store = RASCStore(self.hass)
        self._states: dict[str, RASCState] = {}

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
        component = self.hass.data.get(service_call.domain)
        if not component or not hasattr(component, "async_get_platforms"):
            return
        entity_ids = self._get_entity_ids(service_call)
        platforms = component.async_get_platforms(entity_ids)
        for platform, entities in platforms:
            for entity in entities:
                self._states[entity.entity_id].start_tracking(platform)

    def _init_states(self, context: Context, service_call: ServiceCall):
        component = self.hass.data.get(service_call.domain)
        if not component or not hasattr(component, "async_get_platforms"):
            return
        entity_ids = self._get_entity_ids(service_call)
        platforms = component.async_get_platforms(entity_ids)
        for _, entities in platforms:
            for entity in entities:
                self._states[entity.entity_id] = self._get_rasc_state(
                    context, entity, service_call
                )

    def _get_current_entity_state(self, entity: Entity) -> dict[str, Any]:
        return entity.get_current_state

    def _get_action_complete_percentage(self, state: RASCState) -> float:
        entity = state.entity
        request_state = state.request_state
        action = {
            CONF_SERVICE: state.service_call.service,
            CONF_SERVICE_DATA: state.service_call.data,
        }
        return entity.get_action_complete_percentage(request_state, action)

    def _get_action_length_estimate(self, state: RASCState) -> float:
        prev_length_estimate = state.length_estimate
        current_progress = self._get_action_complete_percentage(state)
        state.length_estimate = prev_length_estimate / current_progress
        return state.length_estimate

    def get_action_length_estimate(
        self,
        entity_id: str,
        action: str | None = None,
        transition: float | None = None,
        quart: float | None = None,
    ) -> float:
        """Get an action length estimate."""
        state = self._states.get(entity_id)
        if not state:
            if not action:
                raise ValueError("action must be provided.")
            if not transition:
                transition = 0.0
            key = ",".join((entity_id, action, str(transition)))
            histories = self._store.histories
            if key not in histories:
                histories[key] = RASCHistory()
            history = histories[key].ct_history
            if not history:
                return transition
            dist = get_best_distribution(history)
            if not quart:
                quart = 0.99
            return dist.ppf(quart)

        return self._get_action_length_estimate(state)

    def _get_rasc_state(
        self, context: Context, entity: Entity, service_call: ServiceCall
    ) -> RASCState:
        """Get RASC state on the given Event e."""
        request_state = self._get_current_entity_state(entity)
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
        return RASCState(
            context,
            entity,
            service_call,
            request_state,
            start_state,
            complete_state,
            self._store,
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

    async def _update_state(self, state: RASCState) -> None:
        """Update RASC and fire responses if any."""

        # check complete state
        complete_state_matched = self._match_state(state, state.complete_state)
        # prevent hazardous changes
        transition = state.transition
        if complete_state_matched and (
            transition is None or state.time_elapsed > transition / 2
        ):
            # fire start response if haven't
            if not state.started:
                await state.set_started()
                self._fire_by_state(RASC_START, state)

            self._fire_by_state(RASC_COMPLETE, state)
            await state.set_completed()
            self._update_store(
                state.entity,
                state.service_call.service,
                state.transition,
                time_to_complete=state.time_elapsed,
            )

            return

        start_state_matched = self._match_state(state, state.start_state)
        if start_state_matched and not state.started:
            self._fire_by_state(RASC_START, state)
            await state.set_started()
            self._update_store(
                state.entity,
                state.service_call.service,
                state.transition,
                time_to_start=state.time_elapsed,
            )
        return

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
            action_id = None
            action = None
            group_id = None
        else:
            entity_id = state.entity.entity_id
            action_id = (
                state.service_call.data[ATTR_ACTION_ID]
                if ATTR_ACTION_ID in state.service_call.data
                else None
            )
            action = state.service_call.service
            group_id = state.service_call.data.get(ATTR_GROUP_ID)
        self._fire(rasc_type, entity_id, action_id, action, group_id)

    def _fire(
        self,
        rasc_type: str,
        entity_id: str | None,
        action_id: str | None,
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
                ATTR_ACTION_ID: action_id,
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
        rasc_state = self._states.get(entity.entity_id)
        if not rasc_state:
            return
        await self._update_state(rasc_state)
        if rasc_state.completed or rasc_state.failed:
            # TODO: add garbage collection # pylint: disable=fixme
            # del self._states[entity.entity_id]
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

        # for response wait-notify
        s_cv = asyncio.Condition()
        c_cv = asyncio.Condition()
        f_cv = asyncio.Condition()
        context = Context(s_cv, c_cv, f_cv)

        self._init_states(context, service_call)

        async def a_future(
            context: Context, handler: Service, service_call: ServiceCall
        ) -> ServiceResponse:
            entity_ids = self._get_entity_ids(service_call)
            action_id = service_call.data.get(ATTR_ACTION_ID)

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

            # TODO: track entities independently (service._handle_entity_call) # pylint: disable=fixme
            # start tracking after receiving ack
            for entity_id in entity_ids:
                self._fire(RASC_ACK, entity_id, action_id, service_call.service)
            self._track_service(context, service_call)
            return response

        async def s_future(
            context: Context, service_call: ServiceCall
        ) -> ServiceResponse:
            entity_ids = self._get_entity_ids(service_call)

            def check_started() -> bool:
                for entity_id in entity_ids:
                    if not self._states[entity_id].started:
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
                for entity_id in entity_ids:
                    if not self._states[entity_id].completed:
                        return False
                return True

            async with context.c_cv:
                await context.c_cv.wait_for(check_completed)
                # notify failure detector to end listening
                async with context.f_cv:
                    context.f_cv.notify()
                return entity_ids

        async def failure_timeout(context: Context, service_call: ServiceCall) -> None:
            entity_ids = self._get_entity_ids(service_call)

            async with context.f_cv:
                await context.f_cv.wait_for(
                    lambda: all(
                        self._states[entity_id].failed
                        or self._states[entity_id].completed
                        for entity_id in entity_ids
                    )
                )

                successful_actions = []
                failed_actions = []
                for entity_id in entity_ids:
                    if self._states[entity_id].failed:
                        failed_actions.append(entity_id)
                    else:
                        successful_actions.append(entity_id)
                message = {
                    "action": service_call.service,
                    "successful": successful_actions,
                    "failed": failed_actions,
                }
                if failed_actions:
                    # prevent infinite recursion
                    if service_call.domain != notify.DOMAIN:
                        notification = {
                            "message": json.dumps(message, indent=2),
                            "title": "Action Failed",
                        }
                        await self.hass.services.async_call(
                            notify.DOMAIN,
                            notify.SERVICE_PERSISTENT_NOTIFICATION,
                            notification,
                        )

        self.hass.async_create_task(failure_timeout(context, service_call))
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
        # no history is found, polling statically
        if history is None or len(history) == 0:
            self._static = True
            # TODO: upper bound shouldn't be None # pylint: disable=fixme
            self._attr_upper_bound = None
            return
        self._static = False
        self._cur_poll = 0
        # only one data in history, poll exactly on that moment
        if len(history) == 1:
            self._polls = [history[0]]
            # TODO: upper bound shouldn't be None # pylint: disable=fixme
            self._attr_upper_bound = None
            return
        # TODO: put this in bg # pylint: disable=fixme
        dist = get_best_distribution(history)
        self._attr_upper_bound = dist.ppf(0.99)
        self._polls = get_polls(dist, self._attr_upper_bound)

    @property
    def upper_bound(self) -> float | None:
        """Return upper bound."""
        return self._attr_upper_bound

    def next_interval(self) -> timedelta:
        """Get next interval."""
        if self._static:
            return timedelta(seconds=1)
        if self._cur_poll < len(self._polls):
            cur = self._cur_poll
            self._cur_poll += 1
            return timedelta(seconds=self._polls[cur])
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
        request_state: dict[str, StateType],
        start_state: dict[str, Any],
        complete_state: dict[str, Any],
        store: RASCStore,
        length_estimate: float = 0,
    ) -> None:
        """Init rasc state."""
        transition: float = service_call.data.get("transition", 0)
        self.request_state = request_state
        self.start_state = start_state
        self.complete_state = complete_state
        self.transition = transition
        self.length_estimate = length_estimate
        self.service_call = service_call
        self.entity = entity
        self._attr_failed = False
        self._attr_started = False
        self._attr_completed = False
        self._context = context
        self._store = store
        self._next_response = RASC_ACK
        # tracking
        self._tracking_task: asyncio.Task[Any] | None = None
        self._s_detector: StateDetector | None = None
        self._c_detector: StateDetector | None = None
        self._exec_time: float | None = None

    @property
    def time_elapsed(self) -> float:
        """Return the elapsed time since started."""
        if not self._exec_time:
            return 0
        return time.time() - self._exec_time

    @property
    def failed(self) -> bool:
        """Return if the action has failed."""
        return self._attr_failed

    @property
    def started(self) -> bool:
        """Return if the action has started."""
        return self._attr_started

    @property
    def completed(self) -> bool:
        """Return if the action has completed."""
        return self._attr_completed

    def start_tracking(self, platform: EntityPlatform | DataUpdateCoordinator) -> None:
        """Start tracking the state."""
        self._next_response = RASC_START
        self._exec_time = time.time()
        coordinator: DataUpdateCoordinator | None = getattr(
            self.entity, "coordinator", None
        )
        if self.entity.should_poll or coordinator:
            key = ",".join(
                (self.entity.entity_id, self.service_call.service, str(self.transition))
            )
            history = self._store.histories.get(key, RASCHistory())
            self._s_detector = StateDetector(history.st_history)
            self._c_detector = StateDetector(history.ct_history)
            # fire failure if exceed upper_bound
            if self._s_detector.upper_bound and self._c_detector.upper_bound:
                upper_bound = (
                    self._s_detector.upper_bound + self._c_detector.upper_bound
                )
                async_track_point_in_time(
                    self.entity.hass,
                    self.set_failed,
                    # TODO: get closer upper_bound # pylint: disable=fixme
                    dt_util.utcnow() + timedelta(seconds=upper_bound * 1.5),
                )
            # let platform state polling the state
            next_interval = self.get_polling_interval()
            # poll by coordinator
            if coordinator:
                self._tracking_task = self.entity.hass.async_create_task(
                    coordinator.track_entity_state(self.entity, next_interval)
                )
            # poll by entity platform
            else:
                self._tracking_task = self.entity.hass.async_create_task(
                    platform.track_entity_state(self.entity, next_interval)
                )

    def get_polling_interval(self) -> timedelta:
        """Get polling interval."""
        if self._next_response == RASC_START:
            if not self._s_detector:
                return timedelta(seconds=1)
            return self._s_detector.next_interval()
        if self._next_response == RASC_COMPLETE:
            if not self._c_detector:
                return timedelta(seconds=1)
            return self._c_detector.next_interval()
        return timedelta(seconds=1)

    async def set_failed(self, _: datetime.datetime):
        """Set failed."""
        if self._tracking_task:
            self._tracking_task.cancel()
            self._tracking_task = None
        self._attr_failed = True
        async with self._context.f_cv:
            self._context.f_cv.notify()

    async def set_started(self):
        """Set started."""
        self._exec_time = time.time()
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
    """RASC permanent store."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new config object."""
        self.hass = hass

        self.histories: dict[str, RASCHistory] = {}
        self._store = self._ConfigStore(hass)
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

    def __init__(
        self, s_cv: asyncio.Condition, c_cv: asyncio.Condition, f_cv: asyncio.Condition
    ) -> None:
        """Initialize context."""
        self.s_cv = s_cv
        self.c_cv = c_cv
        self.f_cv = f_cv
