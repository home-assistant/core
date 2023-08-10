"""The Intent integration."""
import logging

import voluptuous as vol

from homeassistant.components import http
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
)
from homeassistant.components.http.data_validator import RequestDataValidator
from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    integration_platform,
    intent,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Intent component."""
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

    return True


class OnOffIntentHandler(intent.ServiceIntentHandler):
    """Intent handler for on/off that handles covers too."""

    async def async_call_service(self, intent_obj: intent.Intent, state: State) -> None:
        """Call service on entity with special case for covers."""
        hass = intent_obj.hass

        if state.domain == COVER_DOMAIN:
            # on = open
            # off = close
            await self._run_then_background(
                hass.async_create_task(
                    hass.services.async_call(
                        COVER_DOMAIN,
                        SERVICE_OPEN_COVER
                        if self.service == SERVICE_TURN_ON
                        else SERVICE_CLOSE_COVER,
                        {ATTR_ENTITY_ID: state.entity_id},
                        context=intent_obj.context,
                        blocking=True,
                    )
                )
            )
            return
          
        elif state.domain == LOCK_DOMAIN:
            # on = lock
            # off = unlock
            await hass.services.async_call(
                LOCK_DOMAIN,
                SERVICE_LOCK if self.service == SERVICE_TURN_ON else SERVICE_UNLOCK,
                {ATTR_ENTITY_ID: state.entity_id},
                context=intent_obj.context,
                blocking=True,
                limit=self.service_timeout,
            )

        elif not hass.services.has_service(state.domain, self.service):
            raise intent.IntentHandleError(
                f"Service {self.service} does not support entity {state.entity_id}"
            )

        # Fall back to homeassistant.turn_on/off
        await super().async_call_service(intent_obj, state)


class GetStateIntentHandler(intent.IntentHandler):
    """Answer questions about entity states."""

    intent_type = intent.INTENT_GET_STATE
    slot_schema = {
        vol.Any("name", "area"): cv.string,
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("device_class"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("state"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the hass intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)

        # Entity name to match
        name: str | None = slots.get("name", {}).get("value")

        # Look up area first to fail early
        area_name = slots.get("area", {}).get("value")
        area: ar.AreaEntry | None = None
        if area_name is not None:
            areas = ar.async_get(hass)
            area = areas.async_get_area(area_name) or areas.async_get_area_by_name(
                area_name
            )
            if area is None:
                raise intent.IntentHandleError(f"No area named {area_name}")

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

        states = list(
            intent.async_match_states(
                hass,
                name=name,
                area=area,
                domains=domains,
                device_classes=device_classes,
                assistant=intent_obj.assistant,
            )
        )

        _LOGGER.debug(
            "Found %s state(s) that matched: name=%s, area=%s, domains=%s, device_classes=%s, assistant=%s",
            len(states),
            name,
            area,
            domains,
            device_classes,
            intent_obj.assistant,
        )

        # Create response
        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER

        success_results: list[intent.IntentResponseTarget] = []
        if area is not None:
            success_results.append(
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.AREA,
                    name=area.name,
                    id=area.id,
                )
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

        for state in states:
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


async def _async_process_intent(hass: HomeAssistant, domain: str, platform):
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
    async def post(self, request, data):
        """Handle intent with name/data."""
        hass = request.app["hass"]
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
            intent_result = intent.IntentResponse(language=language)
            intent_result.async_set_speech("Sorry, I couldn't handle that")

        return self.json(intent_result)
