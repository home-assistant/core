"""Rasc helper."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import timedelta
from logging import getLogger
import time
from typing import Any, TypeVar, cast

import numdifftools as nd
import numpy as np
import scipy.stats as st

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_GROUP_ID,
    ATTR_SERVICE_DATA,
    CONF_EVENT,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    RASC_COMPLETE,
    RASC_RESPONSE,
    RASC_START,
)
from homeassistant.core import Event, HomeAssistant

from .entity import Entity
from .storage import Store
from .template import device_entities

RT = TypeVar("RT")

_LOGGER = getLogger(__name__)

FAILED_TIMEOUT = 300


class StateDetector:
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
        # how to get upper_bound?
        # print(history)
        self.polls = get_polls(dist, max(history), 2)
        # print(self.polls)

    def next_interval(self) -> timedelta:
        """Get next interval."""
        if self.static:
            return timedelta(seconds=1)
        if self.cur_poll < len(self.polls):
            cur = self.cur_poll
            self.cur_poll += 1
            return timedelta(seconds=self.polls[cur])
        return timedelta(seconds=1)


class RASCHistory:
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


class RASCState:
    """RASC State."""

    def __init__(
        self,
        entity: Entity,
        event: Event,
        start_state: dict[str, Any],
        complete_state: dict[str, Any],
        transition: float,
        history: RASCHistory,
    ) -> None:
        """Init rasc state."""
        self.next_response = RASC_START
        self.start_state = start_state
        self.complete_state = complete_state
        self.transition = transition
        self.event = event
        self.entity = entity
        self.s_detector = StateDetector(history.st_history)
        self.c_detector = StateDetector(history.ct_history)
        # metadata
        self.exec_time = time.time()

    @classmethod
    async def create(
        cls,
        entity: Entity,
        event: Event,
        start_state: dict[str, Any],
        complete_state: dict[str, Any],
    ) -> RASCState:
        """Create rasc state."""
        transition: float = event.data[ATTR_SERVICE_DATA].get("transition", 0)
        key = ",".join((entity.entity_id, event.data[CONF_SERVICE], str(transition)))
        rasc_history = await get_rasc_history(entity.hass)
        if key not in rasc_history:
            rasc_history[key] = RASCHistory()
        return RASCState(
            entity, event, start_state, complete_state, transition, rasc_history[key]
        )

    def get_polling_interval(self) -> timedelta | None:
        """Get polling interval."""
        if self.next_response == RASC_START:
            return self.s_detector.next_interval()
        if self.next_response == RASC_COMPLETE:
            return self.c_detector.next_interval()
        return None


async def get_rasc_history(hass: HomeAssistant) -> dict[str, RASCHistory]:
    """Get rasc history."""
    if hass.rasc_store is None:
        hass.rasc_store = RASCStore(hass)
        await hass.rasc_store.async_load()
    return hass.rasc_store.history


def rasc_push_event(func: Callable[..., RT]) -> Callable[..., RT]:
    """RASC decorator for push-based devices."""

    def _wrapper(self: Entity, *args: Any, **kwargs: dict[str, Any]) -> RT:
        rt = func(self, *args, **kwargs)
        if self.async_on_push_event is not None:
            self.async_on_push_event(self)
        return rt

    return _wrapper


async def update_state(
    hass: HomeAssistant,
    entity: Entity,
    action: str,
    transition: float,
    time_to_start: float | None = None,
    time_to_complete: float | None = None,
) -> None:
    """Update rasc state."""
    key = ",".join((entity.entity_id, action, str(transition)))
    rasc_history = await get_rasc_history(hass)
    if key not in rasc_history:
        rasc_history[key] = RASCHistory()

    if time_to_start:
        rasc_history[key].append_s(time_to_start)
    if time_to_complete:
        rasc_history[key].append_c(time_to_complete)
    if hass.rasc_store is None:
        return
    await hass.rasc_store.async_save()


async def rasc_on_command(
    hass: HomeAssistant,
    e: Event,
    entities: Iterable[Entity],
    default_polling_interval: timedelta | None,
    rascal_state_map: dict[str, RASCState],
) -> timedelta | None:
    """Invoke when RASC receives an event."""
    target_entities = get_target_entities(hass, e, entities)
    if len(target_entities) == 0:
        return None
    polling_interval = default_polling_interval
    for target_entity in target_entities:
        rascal_state_map[target_entity.entity_id] = await async_get_rasc_state(
            hass, e, target_entity
        )
        _polling_interval = rascal_state_map[
            target_entity.entity_id
        ].get_polling_interval()
        if _polling_interval is None:
            continue
        if polling_interval is None or _polling_interval < polling_interval:
            polling_interval = _polling_interval
    return polling_interval


def rasc_on_update(
    hass: HomeAssistant,
    default_polling_interval: timedelta | None,
    rascal_state_map: dict[str, RASCState],
) -> tuple[list[Entity], timedelta | None]:
    """Invoke when RASC updates the state."""
    completed_entities = update_rasc_state(hass, rascal_state_map)
    polling_interval = default_polling_interval
    for rasc_state in rascal_state_map.values():
        _polling_interval = rasc_state.get_polling_interval()
        if _polling_interval is None:
            continue
        if polling_interval is None or _polling_interval < polling_interval:
            polling_interval = _polling_interval
    return completed_entities, polling_interval


def get_target_entities(
    hass: HomeAssistant, e: Event, own_entities: Iterable[Entity]
) -> list[Entity]:
    """Get target entities from Event e."""
    entities: list[str] = []
    if ATTR_DEVICE_ID in e.data[ATTR_SERVICE_DATA]:
        entities = entities + [
            entity
            for _device_id in e.data[ATTR_SERVICE_DATA][ATTR_DEVICE_ID]
            for entity in device_entities(hass, _device_id)
        ]
    if ATTR_ENTITY_ID in e.data[ATTR_SERVICE_DATA]:
        if isinstance(e.data[ATTR_SERVICE_DATA][ATTR_ENTITY_ID], str):
            entities = entities + [e.data[ATTR_SERVICE_DATA][ATTR_ENTITY_ID]]
        else:
            entities = entities + e.data[ATTR_SERVICE_DATA][ATTR_ENTITY_ID]

    return [entity for entity in own_entities if entity.entity_id in entities]


async def async_get_rasc_state(
    hass: HomeAssistant, e: Event, entity: Entity
) -> RASCState:
    """Get RASC state on the given Event e."""
    start_state = (
        await entity.async_get_action_target_state(
            {
                CONF_EVENT: RASC_START,
                CONF_SERVICE: e.data[CONF_SERVICE],
                CONF_SERVICE_DATA: e.data[ATTR_SERVICE_DATA],
            }
        )
    ) or {}
    complete_state = (
        await entity.async_get_action_target_state(
            {
                CONF_EVENT: RASC_COMPLETE,
                CONF_SERVICE: e.data[CONF_SERVICE],
                CONF_SERVICE_DATA: e.data[ATTR_SERVICE_DATA],
            }
        )
    ) or {}
    return await RASCState.create(entity, e, start_state, complete_state)


def update_rasc_state(
    hass: HomeAssistant,
    rascal_state_map: dict[str, RASCState],
    entity: Entity | None = None,
) -> list[Entity]:
    """Update RASC and fire responses if any."""
    completed_list: list[Entity] = []
    for entity_id, state in list(rascal_state_map.items()):
        if entity and entity.entity_id != entity_id:
            continue

        # check complete state
        complete_state_matched = True
        for attr, match in state.complete_state.items():
            if not match(getattr(entity or state.entity, attr)):
                complete_state_matched = False
                break
        # prevent hazardous changes
        transition = state.transition
        if complete_state_matched and (
            transition is None or time.time() - state.exec_time > transition / 2
        ):
            if state.next_response == RASC_START:
                _LOGGER.info("Fire %s response: %s", RASC_START, entity_id)
                hass.bus.async_fire(
                    RASC_RESPONSE,
                    {
                        "type": RASC_START,
                        ATTR_ENTITY_ID: entity_id,
                        ATTR_GROUP_ID: state.event.data.get(ATTR_SERVICE_DATA, {}).get(
                            ATTR_GROUP_ID
                        ),
                    },
                )
            _LOGGER.info("Fire %s response: %s", RASC_COMPLETE, entity_id)
            hass.bus.async_fire(
                RASC_RESPONSE,
                {
                    "type": RASC_COMPLETE,
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_GROUP_ID: state.event.data.get(ATTR_SERVICE_DATA, {}).get(
                        ATTR_GROUP_ID
                    ),
                },
            )
            time_to_complete = time.time() - state.exec_time
            hass.loop.create_task(
                update_state(
                    hass,
                    entity or state.entity,
                    state.event.data[CONF_SERVICE],
                    state.transition,
                    time_to_complete=time_to_complete,
                )
            )

            completed_list.append(entity or state.entity)
            del rascal_state_map[entity_id]
            continue

        start_state_matched = True
        for attr, match in state.start_state.items():
            if not match(getattr(entity or state.entity, attr)):
                start_state_matched = False
                break
        if start_state_matched and state.next_response == RASC_START:
            _LOGGER.info("Fire %s response: %s", RASC_START, entity_id)
            hass.bus.async_fire(
                RASC_RESPONSE,
                {
                    "type": RASC_START,
                    ATTR_ENTITY_ID: entity_id,
                    ATTR_GROUP_ID: state.event.data.get(ATTR_SERVICE_DATA, {}).get(
                        ATTR_GROUP_ID
                    ),
                },
            )
            state.next_response = RASC_COMPLETE
            time_to_start = time.time() - state.exec_time
            state.exec_time = time.time()
            hass.loop.create_task(
                update_state(
                    hass,
                    entity or state.entity,
                    state.event.data[CONF_SERVICE],
                    state.transition,
                    time_to_start=time_to_start,
                )
            )
    return completed_list


def _get_polling_interval(dist: Any, num_poll: int, upper_bound: float) -> list[float]:
    return _get_polling_interval_r(dist, num_poll, upper_bound, 0.0, upper_bound)


def _get_polling_interval_r(
    dist: Any,
    num_poll: int,
    upper_bound: float,
    left: float,
    right: float,
) -> list[float]:
    integral: Callable[[float, float], float] = lambda x, y: dist.cdf(y) - dist.cdf(x)
    L = [0.0 for _ in range(num_poll + 1)]
    # L0 is 0
    # randomized L1
    L[1] = (left + right) / 2
    if left == right:
        raise ValueError("left == right")
    too_large = False
    for n in range(2, num_poll + 1):
        L[n] = 1 / dist.pdf(L[n - 1]) * (integral(L[n - 2], L[n - 1])) + L[n - 1]
        if L[n] > upper_bound:
            too_large = True
            break
    if np.isclose(L[num_poll], upper_bound):
        L[num_poll] = upper_bound
        return L[1:]
    # L1 is too large
    if too_large:
        return _get_polling_interval_r(
            dist,
            num_poll,
            upper_bound,
            left,
            L[1],
        )
    # L1 is too small
    return _get_polling_interval_r(
        dist,
        num_poll,
        upper_bound,
        L[1],
        right,
    )


def _examinate_2nd_derivate(dist: Any, L: list[float]) -> bool:
    # examinate 2nd derivative
    pdf_prime = nd.Derivative(dist.pdf)
    for i, _ in enumerate(L):
        if i == len(L) - 1:
            return True
        val = 2 * dist.pdf(L[i]) - (L[i + 1] - L[i]) * pdf_prime(L[i])
        if val <= 0:
            return False
    return True


def _examinate_delta(dist: Any, L: list[float], worst_delta: float) -> bool:
    qouta = 0.01
    _max = 0.0
    L = [0.0] + L
    for i in range(1, len(L)):
        d = L[i] - L[i - 1]
        if d > _max:
            undetected = dist.cdf(L[i] - worst_delta) - dist.cdf(L[i - 1])
            if undetected > 0:
                qouta -= undetected
            if qouta < 0:
                _max = d
    return _max <= worst_delta


def get_polls(
    dist: Any, upper_bound: float, worst_case_delta: float, name: str = "_"
) -> list[float]:
    """Get polls based on distribution."""
    N = 1
    L = None
    while True:
        L = _get_polling_interval(dist, N, upper_bound)
        valid = _examinate_2nd_derivate(dist, L)
        if not valid:
            print("The result for", name, "is probably not minimized.")  # noqa: T201
        valid = _examinate_delta(dist, L, worst_case_delta)
        if valid:
            break
        N += 1
    return L


def get_best_distribution(data: list[float]) -> Any:
    """Get distribution based on p value."""
    if len(data) == 1:
        return st.uniform(0, data[0])
    dist_names = [
        "uniform",
        "norm",
        "gamma",
        "genlogistic",
    ]
    dist_results = []
    params = {}
    for dist_name in dist_names:
        dist = getattr(st, dist_name)
        param = dist.fit(data)

        params[dist_name] = param
        # Applying the Kolmogorov-Smirnov test
        _, p = st.kstest(data, dist_name, args=param)
        # print("p value for " + dist_name + " = " + str(p))
        dist_results.append((dist_name, p))

    # select the best fitted distribution
    best_dist, _ = max(dist_results, key=lambda item: item[1])
    # store the name of the best fit and its p value

    _LOGGER.info(
        "Best fitting distribution: %s%s", str(best_dist), str(params[best_dist])
    )
    # print("Best p value: " + str(best_p))

    return getattr(st, best_dist)(*params[best_dist])


class RASCStore:
    """RASC perminent store."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize a new config object."""
        self.hass = hass

        self._store = self._ConfigStore(hass)
        self.history: dict[str, RASCHistory] = {}
        self._init_lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load stored data."""
        async with self._init_lock:
            if (data := await self._store.async_load()) is None:
                data = cast(dict[str, dict[str, list[float]]], {})

            self.history = {key: RASCHistory(**hist) for key, hist in data.items()}

    async def async_save(self) -> None:
        """Store data."""
        await self._store.async_save(
            {
                key: {
                    "st_history": hist.st_history,
                    "ct_history": hist.ct_history,
                }
                for key, hist in self.history.items()
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
