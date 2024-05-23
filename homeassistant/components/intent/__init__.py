"""The Intent integration."""

from __future__ import annotations

import logging
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

from .const import DOMAIN, TIMER_DATA
from .timers import (
    CancelTimerIntentHandler,
    DecreaseTimerIntentHandler,
    IncreaseTimerIntentHandler,
    PauseTimerIntentHandler,
    StartTimerIntentHandler,
    TimerManager,
    TimerStatusIntentHandler,
    UnpauseTimerIntentHandler,
    async_register_timer_handler,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

__all__ = [
    "async_register_timer_handler",
    "DOMAIN",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Intent component."""
    hass.data[TIMER_DATA] = TimerManager(hass)

    hass.http.register_view(IntentHandleView())

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _async_process_intent
    )

    intent.async_register(
        hass,
        OnOffIntentHandler(
            intent.INTENT_TURN_ON,
            HA_DOMAIN,
            SERVICE_TURN_ON,
            description="Turns on/opens a device or entity",
        ),
    )
    intent.async_register(
        hass,
        OnOffIntentHandler(
            intent.INTENT_TURN_OFF,
            HA_DOMAIN,
            SERVICE_TURN_OFF,
            description="Turns off/closes a device or entity",
        ),
    )
    intent.async_register(
        hass,
        intent.ServiceIntentHandler(
            intent.INTENT_TOGGLE,
            HA_DOMAIN,
            SERVICE_TOGGLE,
            "Toggles a device or entity",
        ),
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
    intent.async_register(hass, StartTimerIntentHandler())
    intent.async_register(hass, CancelTimerIntentHandler())
    intent.async_register(hass, IncreaseTimerIntentHandler())
    intent.async_register(hass, DecreaseTimerIntentHandler())
    intent.async_register(hass, PauseTimerIntentHandler())
    intent.async_register(hass, UnpauseTimerIntentHandler())
    intent.async_register(hass, TimerStatusIntentHandler())

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
    description = "Gets or checks the state of a device or entity"
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
    description = "Cancels the current request and does nothing"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Doe not do anything, and produces an empty response."""
        return intent_obj.create_response()


class SetPositionIntentHandler(intent.DynamicServiceIntentHandler):
    """Intent handler for setting positions."""

    description = "Sets the position of a device or entity"

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
