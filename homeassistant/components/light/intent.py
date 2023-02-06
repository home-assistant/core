"""Intents for the light integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry, config_validation as cv, intent
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


class SetIntentHandler(intent.IntentHandler):
    """Handle set color intents."""

    intent_type = INTENT_SET
    slot_schema = {
        vol.Any("name", "area"): cv.string,
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("device_class"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("color"): color_util.color_name_to_rgb,
        vol.Optional("brightness"): vol.All(vol.Coerce(int), vol.Range(0, 100)),
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Handle the hass intent."""
        hass = intent_obj.hass
        service_data: dict[str, Any] = {}
        slots = self.async_validate_slots(intent_obj.slots)

        name: str | None = slots.get("name", {}).get("value")
        if name == "all":
            # Don't match on name if targeting all entities
            name = None

        # Look up area first to fail early
        area_name = slots.get("area", {}).get("value")
        area: area_registry.AreaEntry | None = None
        if area_name is not None:
            areas = area_registry.async_get(hass)
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

        states = list(
            intent.async_match_states(
                hass,
                name=name,
                area=area,
                domains=domains,
                device_classes=device_classes,
            )
        )

        if not states:
            raise intent.IntentHandleError("No entities matched")

        if "color" in slots:
            service_data[ATTR_RGB_COLOR] = slots["color"]["value"]

        if "brightness" in slots:
            service_data[ATTR_BRIGHTNESS_PCT] = slots["brightness"]["value"]

        response = intent_obj.create_response()
        needs_brightness = ATTR_BRIGHTNESS_PCT in service_data
        needs_color = ATTR_RGB_COLOR in service_data

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
                    DOMAIN,
                    SERVICE_TURN_ON,
                    {**service_data, ATTR_ENTITY_ID: state.entity_id},
                    context=intent_obj.context,
                )
            )
            success_results.append(target)

        # Handle service calls in parallel.
        await asyncio.gather(*service_coros)

        response.async_set_results(
            success_results=success_results, failed_results=failed_results
        )

        return response
