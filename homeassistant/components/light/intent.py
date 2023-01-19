"""Intents for the light integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry, intent
import homeassistant.util.color as color_util

from . import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN,
    brightness_supported,
    color_supported,
)

_LOGGER = logging.getLogger(__name__)

INTENT_SET = "HassLightSet"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the light intents."""
    intent.async_register(hass, SetIntentHandler())


class SetIntentHandler(intent.ServiceIntentHandler):
    """Handle set color intents."""

    intent_type = INTENT_SET
    slot_schema = {
        **intent.ServiceIntentHandler.slot_schema,
        vol.Optional("color"): color_util.color_name_to_rgb,
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
    }

    def __init__(self) -> None:
        """Initialize SetIntentHandler."""
        super().__init__(INTENT_SET, DOMAIN, SERVICE_TURN_ON, "Turned on {}")
        self.service_data: dict[str, Any] = {}
        self.speech_parts: list[str] = []
        _LOGGER.info(self.slot_schema)

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the hass intent."""
        self.service_data = {}
        self.speech_parts = []

        slots = self.async_validate_slots(intent_obj.slots)

        if "color" in slots:
            self.service_data[ATTR_RGB_COLOR] = slots["color"]["value"]
            # Use original passed in value of the color because we don't have
            # human readable names for that internally.
            self.speech_parts.append(f"the color {intent_obj.slots['color']['value']}")

        if "brightness" in slots:
            self.service_data[ATTR_BRIGHTNESS_PCT] = slots["brightness"]["value"]
            self.speech_parts.append(f"{slots['brightness']['value']}% brightness")

        response = await super().async_handle(intent_obj)
        return response

    async def async_handle_states(
        self,
        intent_obj: intent.Intent,
        states: list[State],
        area: area_registry.AreaEntry | None = None,
    ) -> intent.IntentResponse:
        """Complete action on matched entity states."""
        assert states
        hass = intent_obj.hass
        response = intent_obj.create_response()
        needs_brightness = ATTR_BRIGHTNESS_PCT in self.service_data
        needs_color = ATTR_RGB_COLOR in self.service_data

        success_results: list[intent.IntentResponseTarget] = []
        failed_results: list[intent.IntentResponseTarget] = []
        service_coros = []

        if area is not None:
            success_results.append(
                intent.IntentResponseTarget(
                    type=intent.IntentResponseTargetType.AREA,
                    name=area.name,
                    id=area.id,
                )
            )
            speech_name = area.name
        else:
            speech_name = states[0].name

        for state in states:
            target = intent.IntentResponseTarget(
                type=intent.IntentResponseTargetType.ENTITY,
                name=state.name,
                id=state.entity_id,
            )

            # Test brightness/color
            supported_color_modes = state.attributes.get(ATTR_SUPPORTED_COLOR_MODES)
            if (needs_color and not color_supported(supported_color_modes)) or (
                needs_brightness and not brightness_supported(supported_color_modes)
            ):
                failed_results.append(target)
                continue

            service_coros.append(
                hass.services.async_call(
                    self.domain,
                    self.service,
                    {**self.service_data, ATTR_ENTITY_ID: state.entity_id},
                    context=intent_obj.context,
                )
            )
            success_results.append(target)

        # Handle service calls in parallel.
        await asyncio.gather(*service_coros)

        response.async_set_results(
            success_results=success_results, failed_results=failed_results
        )

        if not self.speech_parts:  # No attributes changed
            speech = f"Turned on {speech_name}"
        else:
            parts = [f"Changed {speech_name} to"]
            for index, part in enumerate(self.speech_parts):
                if index == 0:
                    parts.append(f" {part}")
                elif index != len(self.speech_parts) - 1:
                    parts.append(f", {part}")
                else:
                    parts.append(f" and {part}")
            speech = "".join(parts)

        response.async_set_speech(speech)

        return response
