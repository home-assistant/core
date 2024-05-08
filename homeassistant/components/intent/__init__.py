"""The Intent integration."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
import logging
import time
from typing import Any, Protocol

from aiohttp import web
import voluptuous as vol

from homeassistant.components import http
from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
)
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.components.valve import (
    DOMAIN as VALVE_DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant, State
from homeassistant.helpers import config_validation as cv, integration_platform, intent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import ulid

from .const import DOMAIN, TIMER_DATA

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Intent component."""
    hass.data[TIMER_DATA] = TimerManager(hass)

    hass.http.register_view(IntentHandleView())

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _async_process_intent
    )

    intent.async_register(
        hass,
        OnOffIntentHandler(intent.INTENT_TURN_ON, HA_DOMAIN, SERVICE_TURN_ON),
    )
    intent.async_register(
        hass,
        OnOffIntentHandler(intent.INTENT_TURN_OFF, HA_DOMAIN, SERVICE_TURN_OFF),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(intent.INTENT_TOGGLE, HA_DOMAIN, SERVICE_TOGGLE),
    )
    intent.async_register(
        hass,
        GetStateIntentHandler(),
    )
    intent.async_register(
        hass,
        NevermindIntentHandler(),
    )
    intent.async_register(hass, SetPositionIntentHandler())
    intent.async_register(hass, SetTimerIntentHandler())
    intent.async_register(hass, CancelTimerIntentHandler())
    intent.async_register(hass, IncreaseTimerIntentHandler())
    intent.async_register(hass, DecreaseTimerIntentHandler())

    return True


class IntentPlatformProtocol(Protocol):
    """Define the format that intent platforms can have."""

    async def async_setup_intents(self, hass: HomeAssistant) -> None:
        """Set up platform intents."""


class OnOffIntentHandler(intent.ServiceIntentHandler):
    """Intent handler for on/off that also supports covers, valves, locks, etc."""

    async def async_call_service(
        self, domain: str, service: str, intent_obj: intent.Intent, state: State
    ) -> None:
        """Call service on entity with handling for special cases."""
        hass = intent_obj.hass

        if state.domain == COVER_DOMAIN:
            # on = open
            # off = close
            if service == SERVICE_TURN_ON:
                service_name = SERVICE_OPEN_COVER
            else:
                service_name = SERVICE_CLOSE_COVER

            await self._run_then_background(
                hass.async_create_task(
                    hass.services.async_call(
                        COVER_DOMAIN,
                        service_name,
                        {ATTR_ENTITY_ID: state.entity_id},
                        context=intent_obj.context,
                        blocking=True,
                    )
                )
            )
            return

        if state.domain == LOCK_DOMAIN:
            # on = lock
            # off = unlock
            if service == SERVICE_TURN_ON:
                service_name = SERVICE_LOCK
            else:
                service_name = SERVICE_UNLOCK

            await self._run_then_background(
                hass.async_create_task(
                    hass.services.async_call(
                        LOCK_DOMAIN,
                        service_name,
                        {ATTR_ENTITY_ID: state.entity_id},
                        context=intent_obj.context,
                        blocking=True,
                    )
                )
            )
            return

        if state.domain == VALVE_DOMAIN:
            # on = opened
            # off = closed
            if service == SERVICE_TURN_ON:
                service_name = SERVICE_OPEN_VALVE
            else:
                service_name = SERVICE_CLOSE_VALVE

            await self._run_then_background(
                hass.async_create_task(
                    hass.services.async_call(
                        VALVE_DOMAIN,
                        service_name,
                        {ATTR_ENTITY_ID: state.entity_id},
                        context=intent_obj.context,
                        blocking=True,
                    )
                )
            )
            return

        if not hass.services.has_service(state.domain, service):
            raise intent.IntentHandleError(
                f"Service {service} does not support entity {state.entity_id}"
            )

        # Fall back to homeassistant.turn_on/off
        await super().async_call_service(domain, service, intent_obj, state)


class GetStateIntentHandler(intent.IntentHandler):
    """Answer questions about entity states."""

    intent_type = intent.INTENT_GET_STATE
    slot_schema = {
        vol.Any("name", "area", "floor"): cv.string,
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("device_class"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("state"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        # Entity name to match
        name_slot = slots.get("name", {})
        entity_name: str | None = name_slot.get("value")

        # Get area/floor info
        area_slot = slots.get("area", {})
        area_id = area_slot.get("value")

        floor_slot = slots.get("floor", {})
        floor_id = floor_slot.get("value")

        # Optional domain/device class filters.
        # Convert to sets for speed.
        domains: set[str] | None = None
        device_classes: set[str] | None = None

        if "domain" in slots:
            domains = set(slots["domain"]["value"])

        if "device_class" in slots:
            device_classes = set(slots["device_class"]["value"])

        state_names: set[str] | None = None
        if "state" in slots:
            state_names = set(slots["state"]["value"])

        match_constraints = intent.MatchTargetsConstraints(
            name=entity_name,
            area_name=area_id,
            floor_name=floor_id,
            domains=domains,
            device_classes=device_classes,
            assistant=intent_obj.assistant,
        )
        match_result = intent.async_match_targets(hass, match_constraints)
        if (
            (not match_result.is_match)
            and (match_result.no_match_reason is not None)
            and (not match_result.no_match_reason.is_no_entities_reason())
        ):
            # Don't try to answer questions for certain errors.
            # Other match failure reasons are OK.
            raise intent.MatchFailedError(
                result=match_result, constraints=match_constraints
            )

        # Create response
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER

        success_results: list[intent.IntentResponseTarget] = []
        if match_result.areas:
            success_results.extend(
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.AREA,
                    name=area.name,
                    id=area.id,
                )
                for area in match_result.areas
            )

        if match_result.floors:
            success_results.extend(
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.FLOOR,
                    name=floor.name,
                    id=floor.floor_id,
                )
                for floor in match_result.floors
            )

        # If we are matching a state name (e.g., "which lights are on?"), then
        # we split the filtered states into two groups:
        #
        # 1. matched - entity states that match the requested state ("on")
        # 2. unmatched - entity states that don't match ("off")
        #
        # In the response template, we can access these as query.matched and
        # query.unmatched.
        matched_states: list[State] = []
        unmatched_states: list[State] = []

        for state in match_result.states:
            success_results.append(
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.ENTITY,
                    name=state.name,
                    id=state.entity_id,
                ),
            )

            if (not state_names) or (state.state in state_names):
                # If no state constraint, then all states will be "matched"
                matched_states.append(state)
            else:
                unmatched_states.append(state)

        response.async_set_results(success_results=success_results)
        response.async_set_states(matched_states, unmatched_states)

        return response


class NevermindIntentHandler(intent.IntentHandler):
    """Takes no action."""

    intent_type = intent.INTENT_NEVERMIND

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Doe not do anything, and produces an empty response."""
        return intent_obj.create_response()


class SetPositionIntentHandler(intent.DynamicServiceIntentHandler):
    """Intent handler for setting positions."""

    def __init__(self) -> None:
        """Create set position handler."""
        super().__init__(
            intent.INTENT_SET_POSITION,
            required_slots={
                ATTR_POSITION: vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
            },
        )

    def get_domain_and_service(
        self, intent_obj: intent.Intent, state: State
    ) -> tuple[str, str]:
        """Get the domain and service name to call."""
        if state.domain == COVER_DOMAIN:
            return (COVER_DOMAIN, SERVICE_SET_COVER_POSITION)

        if state.domain == VALVE_DOMAIN:
            return (VALVE_DOMAIN, SERVICE_SET_VALVE_POSITION)

        raise intent.IntentHandleError(f"Domain not supported: {state.domain}")


class TimerEventType(StrEnum):
    """Timer event type."""

    STARTED = "started"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    UPDATED = "updated"


@dataclass(frozen=True)
class TimerEvent:
    """Event sent when a timer changes state."""

    type: TimerEventType
    timer_id: str
    seconds_left: int
    name: str | None = None


@dataclass
class TimerInfo:
    """Information for a single timer."""

    id: str
    name: str | None
    seconds: int
    device_id: str
    task: asyncio.Task
    start_hours: int | None
    start_minutes: int | None
    start_seconds: int | None

    updated_at: int
    """Timestamp when timer was last updated (set with time.monotonic_ns)"""

    @property
    def seconds_left(self) -> int:
        """Return number of seconds left on the timer."""
        now = time.monotonic_ns()
        seconds_running = int((now - self.updated_at) / 1e9)
        return max(0, self.seconds - seconds_running)


TimerHandler = Callable[[TimerEvent], Coroutine[Any, Any, None]]


class TimerManager:
    """Manager for intent timers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize timer manager."""
        self.hass = hass

        # timer id -> timer
        self.timers: dict[str, TimerInfo] = {}

        # device id -> handlers
        self.handlers: dict[str, list[TimerHandler]] = defaultdict(list)

    def register_handler(
        self, device_id: str, handler: TimerHandler
    ) -> Callable[[], None]:
        """Register a timer event handler for a device."""
        self.handlers[device_id].append(handler)

        return lambda: self.handlers[device_id].remove(handler)

    async def start_timer(
        self,
        device_id: str,
        hours: int | None,
        minutes: int | None,
        seconds: int | None,
        name: str | None = None,
    ) -> str:
        """Start a timer."""
        total_seconds = 0
        if hours is not None:
            total_seconds += 60 * 60 * hours

        if minutes is not None:
            total_seconds += 60 * minutes

        if seconds is not None:
            total_seconds += seconds

        timer_id = ulid.ulid_now()
        created_at = time.monotonic_ns()
        self.timers[timer_id] = TimerInfo(
            id=timer_id,
            name=name,
            start_hours=hours,
            start_minutes=minutes,
            start_seconds=seconds,
            seconds=total_seconds,
            device_id=device_id,
            task=self.hass.async_create_background_task(
                self._wait_for_timer(timer_id, total_seconds, created_at),
                name=f"Timer {timer_id}",
            ),
            updated_at=created_at,
        )

        event = TimerEvent(
            TimerEventType.STARTED, timer_id, name=name, seconds_left=total_seconds
        )
        await asyncio.gather(*(handler(event) for handler in self.handlers[device_id]))

        return timer_id

    async def _wait_for_timer(
        self, timer_id: str, seconds: int, updated_at: int
    ) -> None:
        """Sleep until timer is up. Timer is only finished if it hasn't been updated."""
        try:
            await asyncio.sleep(seconds)
            if (timer := self.timers.get(timer_id)) and (
                timer.updated_at == updated_at
            ):
                await self._timer_finished(timer_id, timer.device_id)
        except asyncio.CancelledError:
            pass  # expected when timer is updated

    def find_timer_by_name(self, name: str) -> str | None:
        """Find a timer by name."""
        for timer in self.timers.values():
            if timer.name == name:
                return timer.id

        return None

    def find_timer_by_start(
        self, hours: int | None, minutes: int | None, seconds: int | None
    ) -> str | None:
        """Find a timer by its starting time."""
        for timer in self.timers.values():
            if (
                (timer.start_hours == hours)
                and (timer.start_minutes == minutes)
                and (timer.start_seconds == seconds)
            ):
                return timer.id

        return None

    async def cancel_timer(self, timer_id: str) -> None:
        """Cancel a timer."""
        if timer := self.timers.pop(timer_id, None):
            timer.seconds = 0
            timer.updated_at = time.monotonic_ns()
            timer.task.cancel()
            event = TimerEvent(
                TimerEventType.CANCELLED, timer_id, name=timer.name, seconds_left=0
            )
            await asyncio.gather(
                *(handler(event) for handler in self.handlers[timer.device_id])
            )

    async def add_time(self, timer_id: str, seconds: int) -> None:
        """Add time to a timer."""
        if timer := self.timers.get(timer_id):
            timer.seconds = max(0, timer.seconds_left + seconds)
            timer.updated_at = time.monotonic_ns()
            timer.task.cancel()
            timer.task = self.hass.async_create_background_task(
                self._wait_for_timer(timer_id, timer.seconds, timer.updated_at),
                name=f"Timer {timer_id}",
            )
            event = TimerEvent(
                TimerEventType.UPDATED,
                timer_id,
                name=timer.name,
                seconds_left=timer.seconds,
            )
            await asyncio.gather(
                *(handler(event) for handler in self.handlers[timer.device_id])
            )

    async def remove_time(self, timer_id: str, seconds: int) -> None:
        """Remove time from a timer."""
        await self.add_time(timer_id, -seconds)

    async def _timer_finished(self, timer_id: str, device_id: str) -> None:
        """Call event handlers when a timer finishes."""
        if timer := self.timers.pop(timer_id):
            event = TimerEvent(
                TimerEventType.FINISHED, timer_id, name=timer.name, seconds_left=0
            )
            await asyncio.gather(
                *(handler(event) for handler in self.handlers[device_id])
            )


def async_register_timer_handler(
    hass: HomeAssistant, device_id: str, handler: TimerHandler
) -> Callable[[], None]:
    """Register a handler for timer events on a device.

    Returns a function to unregister.
    """
    timer_manager: TimerManager = hass.data[TIMER_DATA]
    return timer_manager.register_handler(device_id, handler)


class SetTimerIntentHandler(intent.IntentHandler):
    """Intent handler for starting a new timer."""

    intent_type = intent.INTENT_SET_TIMER
    slot_schema = {
        vol.Required("device_id"): cv.string,
        vol.Required(vol.Any("hours", "minutes", "seconds")): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        device_id: str = slots["device_id"]["value"]
        name: str | None = None
        if "name" in slots:
            name = slots["name"]["value"]

        hours: int | None = None
        if "hours" in slots:
            hours = int(slots["hours"]["value"])

        minutes: int | None = None
        if "minutes" in slots:
            minutes = int(slots["minutes"]["value"])

        seconds: int | None = None
        if "seconds" in slots:
            seconds = int(slots["seconds"]["value"])

        await timer_manager.start_timer(device_id, hours, minutes, seconds, name=name)

        return intent_obj.create_response()


class CancelTimerIntentHandler(intent.IntentHandler):
    """Intent handler for cancelling running timer."""

    intent_type = intent.INTENT_CANCEL_TIMER
    slot_schema = {
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        response = intent_obj.create_response()

        timer_id: str | None = None
        if "name" in slots:
            name: str = slots["name"]["value"]
            timer_id = timer_manager.find_timer_by_name(name)

            if timer_id is not None:
                # Matched by name
                await timer_manager.cancel_timer(timer_id)
                return response

            response.async_set_error(
                intent.IntentResponseErrorCode.NO_VALID_TARGETS,
                f"No timer named {name}",
            )
            return response

        start_hours: int | None = None
        if "start_hours" in slots:
            start_hours = int(slots["start_hours"]["value"])

        start_minutes: int | None = None
        if "start_minutes" in slots:
            start_minutes = int(slots["start_minutes"]["value"])

        start_seconds: int | None = None
        if "start_seconds" in slots:
            start_seconds = int(slots["start_seconds"]["value"])

        timer_id = timer_manager.find_timer_by_start(
            start_hours, start_minutes, start_seconds
        )
        if timer_id is not None:
            # Matched by starting time
            await timer_manager.cancel_timer(timer_id)
            return response

        response.async_set_error(
            intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            f"No timer for hours={start_hours}, minutes={start_minutes}, seconds={start_seconds}",
        )

        return response


class IncreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for increasing the time of a running timer."""

    intent_type = intent.INTENT_INCREASE_TIMER
    slot_schema = {
        vol.Any("hours", "minutes", "seconds"): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        response = intent_obj.create_response()

        total_seconds = 0
        if "hours" in slots:
            total_seconds += 60 * 60 * int(slots["hours"]["value"])

        if "minutes" in slots:
            total_seconds += 60 * int(slots["minutes"]["value"])

        if "seconds" in slots:
            total_seconds += int(slots["seconds"]["value"])

        timer_id: str | None = None
        if "name" in slots:
            name: str = slots["name"]["value"]
            timer_id = timer_manager.find_timer_by_name(name)

            if timer_id is not None:
                # Matched by name
                await timer_manager.add_time(timer_id, total_seconds)
                return response

            response.async_set_error(
                intent.IntentResponseErrorCode.NO_VALID_TARGETS,
                f"No timer named {name}",
            )
            return response

        start_hours: int | None = None
        if "start_hours" in slots:
            start_hours = int(slots["start_hours"]["value"])

        start_minutes: int | None = None
        if "start_minutes" in slots:
            start_minutes = int(slots["start_minutes"]["value"])

        start_seconds: int | None = None
        if "start_seconds" in slots:
            start_seconds = int(slots["start_seconds"]["value"])

        timer_id = timer_manager.find_timer_by_start(
            start_hours, start_minutes, start_seconds
        )
        if timer_id is not None:
            # Matched by starting time
            await timer_manager.add_time(timer_id, total_seconds)
            return response

        response.async_set_error(
            intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            f"No timer for hours={start_hours}, minutes={start_minutes}, seconds={start_seconds}",
        )

        return response


class DecreaseTimerIntentHandler(intent.IntentHandler):
    """Intent handler for decreasing the time of a running timer."""

    intent_type = intent.INTENT_DECREASE_TIMER
    slot_schema = {
        vol.Any("hours", "minutes", "seconds"): cv.positive_int,
        vol.Any("start_hours", "start_minutes", "start_seconds"): cv.positive_int,
        vol.Optional("name"): cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the intent."""
        hass = intent_obj.hass
        timer_manager: TimerManager = hass.data[TIMER_DATA]
        slots = self.async_validate_slots(intent_obj.slots)

        response = intent_obj.create_response()

        total_seconds = 0
        if "hours" in slots:
            total_seconds += 60 * 60 * int(slots["hours"]["value"])

        if "minutes" in slots:
            total_seconds += 60 * int(slots["minutes"]["value"])

        if "seconds" in slots:
            total_seconds += int(slots["seconds"]["value"])

        timer_id: str | None = None
        if "name" in slots:
            name: str = slots["name"]["value"]
            timer_id = timer_manager.find_timer_by_name(name)

            if timer_id is not None:
                # Matched by name
                await timer_manager.remove_time(timer_id, total_seconds)
                return response

            response.async_set_error(
                intent.IntentResponseErrorCode.NO_VALID_TARGETS,
                f"No timer named {name}",
            )
            return response

        start_hours: int | None = None
        if "start_hours" in slots:
            start_hours = int(slots["start_hours"]["value"])

        start_minutes: int | None = None
        if "start_minutes" in slots:
            start_minutes = int(slots["start_minutes"]["value"])

        start_seconds: int | None = None
        if "start_seconds" in slots:
            start_seconds = int(slots["start_seconds"]["value"])

        timer_id = timer_manager.find_timer_by_start(
            start_hours, start_minutes, start_seconds
        )
        if timer_id is not None:
            # Matched by starting time
            await timer_manager.remove_time(timer_id, total_seconds)
            return response

        response.async_set_error(
            intent.IntentResponseErrorCode.NO_VALID_TARGETS,
            f"No timer for hours={start_hours}, minutes={start_minutes}, seconds={start_seconds}",
        )

        return response


async def _async_process_intent(
    hass: HomeAssistant, domain: str, platform: IntentPlatformProtocol
) -> None:
    """Process the intents of an integration."""
    await platform.async_setup_intents(hass)


class IntentHandleView(http.HomeAssistantView):
    """View to handle intents from JSON."""

    url = "/api/intent/handle"
    name = "api:intent:handle"

    @RequestDataValidator(
        vol.Schema(
            {
                vol.Required("name"): cv.string,
                vol.Optional("data"): vol.Schema({cv.string: object}),
            }
        )
    )
    async def post(self, request: web.Request, data: dict[str, Any]) -> web.Response:
        """Handle intent with name/data."""
        hass = request.app[http.KEY_HASS]
        language = hass.config.language

        try:
            intent_name = data["name"]
            slots = {
                key: {"value": value} for key, value in data.get("data", {}).items()
            }
            intent_result = await intent.async_handle(
                hass, DOMAIN, intent_name, slots, "", self.context(request)
            )
        except intent.IntentHandleError as err:
            intent_result = intent.IntentResponse(language=language)
            intent_result.async_set_speech(str(err))

        if intent_result is None:
            intent_result = intent.IntentResponse(language=language)  # type: ignore[unreachable]
            intent_result.async_set_speech("Sorry, I couldn't handle that")

        return self.json(intent_result)
