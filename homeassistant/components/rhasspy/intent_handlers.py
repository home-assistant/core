"""
Handlers for Rhasspy-specific intents.

For more details about this integration, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import asyncio
import logging
from typing import List

import pydash

from homeassistant.helpers import intent
from homeassistant.helpers.template import Template

from .const import (
    DOMAIN,
    INTENT_DEVICE_STATE,
    INTENT_IS_DEVICE_STATE,
    INTENT_SET_TIMER,
    INTENT_TIMER_READY,
    INTENT_TRIGGER_AUTOMATION,
    INTENT_TRIGGER_AUTOMATION_LATER,
)

# -----------------------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class IsDeviceStateIntent(intent.IntentHandler):
    """Confirms or disconfirms the current state of a device."""

    intent_type = INTENT_IS_DEVICE_STATE
    slot_schema = {"name": str, "state": str}

    def __init__(self, speech_template: Template):
        """Create IsDeviceState intent handler."""
        self.speech_template = speech_template

    async def async_handle(self, intent_obj):
        """Handle intent and generate speech."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["name"]["value"]
        state_name = slots["state"]["value"]
        state = intent.async_match_state(hass, name)

        # Generate speech from a template.
        self.speech_template.hass = hass
        speech = self.speech_template.async_render(
            {"entity": state, "state": state_name}
        )
        _LOGGER.debug(speech)

        response = intent_obj.create_response()
        response.async_set_speech(speech)
        return response


class DeviceStateIntent(intent.IntentHandler):
    """Reports a device's state through speech."""

    intent_type = INTENT_DEVICE_STATE
    slot_schema = {"name": str}

    def __init__(self, speech_template: Template):
        """Create DeviceState intent handler."""
        self.speech_template = speech_template

    async def async_handle(self, intent_obj):
        """Handle intent and generate speech."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["name"]["value"]
        state = intent.async_match_state(hass, name)

        # Generate speech from a template.
        self.speech_template.hass = hass
        speech = self.speech_template.async_render({"entity": state})
        _LOGGER.debug(speech)

        response = intent_obj.create_response()
        response.async_set_speech(speech)
        return response


# -----------------------------------------------------------------------------


def make_state_handler(intent_obj, states: List[str], speech_template: Template):
    """Generate an intent handler that checks if a device is in a set of states."""
    class StateIntent(intent.IntentHandler):
        """Confirm or disconfirm the specific state of a device."""

        intent_type = intent_obj
        slot_schema = {"name": str}

        def __init__(self, states: List[str], speech_template: Template):
            """Create intent handler."""
            self.speech_template = speech_template
            self.states = states

        async def async_handle(self, intent_obj):
            """Handle intent and generate speech."""
            hass = intent_obj.hass
            slots = self.async_validate_slots(intent_obj.slots)
            name = slots["name"]["value"]
            state = intent.async_match_state(hass, name)

            # Generate speech from a template.
            self.speech_template.hass = hass
            speech = self.speech_template.async_render(
                {"entity": state, "states": self.states}
            )
            _LOGGER.debug(speech)

            response = intent_obj.create_response()
            response.async_set_speech(speech)
            return response

    return StateIntent(states, speech_template)


# -----------------------------------------------------------------------------


class SetTimerIntent(intent.IntentHandler):
    """Wait for a specified amount of time and then generate an TimerReady."""

    intent_type = INTENT_SET_TIMER
    slot_schema = {"hours": str, "minutes": str, "seconds": str}

    async def async_handle(self, intent_obj):
        """Wait for timer then generate TimerReady intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        total_seconds = SetTimerIntent.get_seconds(slots)

        # Wait for timer to elapse
        _LOGGER.debug("Waiting for %s second(s)", total_seconds)
        await asyncio.sleep(total_seconds)

        return await intent.async_handle(hass, DOMAIN, INTENT_TIMER_READY, {}, "")

    @classmethod
    def get_seconds(cls, slots) -> int:
        """Compute total number of seconds for timer."""
        total_seconds = 0

        # Time unit values may have multiple parts, like "30 2" for 32.
        for seconds_str in pydash.get(slots, "seconds.value").strip().split():
            total_seconds += int(seconds_str)

        for minutes_str in pydash.get(slots, "minutes.value", "").strip().split():
            total_seconds += int(minutes_str) * 60

        for hours_str in pydash.get(slots, "hours.value", "").strip().split():
            total_seconds += int(hours_str) * 60 * 60

        return total_seconds


class TimerReadyIntent(intent.IntentHandler):
    """Intent generated after SetTimer timeout elapses."""

    intent_type = INTENT_TIMER_READY

    def __init__(self, speech_template: Template):
        """Create TimerReady intent handler."""
        self.speech_template = speech_template

    async def async_handle(self, intent_obj):
        """Handle intent and generate speech."""
        hass = intent_obj.hass

        # Generate speech from a template
        self.speech_template.hass = hass
        speech = self.speech_template.async_render()
        _LOGGER.debug(speech)

        response = intent_obj.create_response()
        response.async_set_speech(speech)
        return response


# -----------------------------------------------------------------------------


class TriggerAutomationIntent(intent.IntentHandler):
    """Trigger an automation by name and generate speech according to a template."""

    intent_type = INTENT_TRIGGER_AUTOMATION
    slot_schema = {"name": str}

    def __init__(self, speech_template: Template):
        """Create TriggerAutomation intent handler."""
        self.speech_template = speech_template

    async def async_handle(self, intent_obj):
        """Trigger automation and generate speech."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["name"]["value"]
        state = intent.async_match_state(hass, name)

        await hass.services.async_call(
            "automation", "trigger", {"entity_id": state.entity_id}
        )

        # Generate speech from a template
        self.speech_template.hass = hass
        speech = self.speech_template.async_render({"automation": state})
        _LOGGER.debug(speech)

        response = intent_obj.create_response()
        response.async_set_speech(speech)
        return response


class TriggerAutomationLaterIntent(intent.IntentHandler):
    """Wait for a specified amount of time and then trigger an automation using TriggerAutomation."""

    intent_type = INTENT_TRIGGER_AUTOMATION_LATER
    slot_schema = {"name": str, "hours": str, "minutes": str, "seconds": str}

    async def async_handle(self, intent_obj):
        """Wait for timeout then generate TriggerAutomation."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        name = slots["name"]["value"]
        state = intent.async_match_state(hass, name)
        total_seconds = SetTimerIntent.get_seconds(slots)

        _LOGGER.debug(
            "Waiting for %s second(s) before triggering %s", total_seconds, name
        )
        await asyncio.sleep(total_seconds)

        # Trigger automation
        await hass.services.async_call(
            "automation", "trigger", {"entity_id": state.entity_id}
        )

        # Use TriggerAutomation
        return await intent.async_handle(
            hass, DOMAIN, INTENT_TRIGGER_AUTOMATION, {"name": name}, ""
        )
