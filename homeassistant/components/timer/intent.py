"""Intents for the timer integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_ID
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_component import EntityComponent

from . import (
    CONF_DURATION,
    CONF_RESTORE,
    DOMAIN,
    EVENT_TIMER_FINISHED,
    SERVICE_START,
    Timer,
)

INTENT_START_DEVICE_TIMER = "HassStartDeviceTimer"

_LOGGER = logging.getLogger()


async def async_setup_intents(hass: HomeAssistant) -> None:
    """Set up the timer intents."""
    intent.async_register(hass, StartDeviceTimerIntent())


async def async_device_timer_finished(hass: HomeAssistant, device_id: str) -> None:
    """Responds to a device when its timer is finished."""


class StartDeviceTimerIntent(intent.IntentHandler):
    """Handle StartDeviceTimer intents."""

    intent_type = INTENT_START_DEVICE_TIMER
    slot_schema = {
        "device_id": str,
        vol.Optional("hours"): int,
        vol.Optional("minutes"): int,
        vol.Optional("seconds"): int,
    }

    async def async_handle(self, intent_obj: intent.Intent):
        """Handle the intent."""
        hass = intent_obj.hass
        slots = self.async_validate_slots(intent_obj.slots)
        device_id = slots["device_id"]["value"]
        entity_id = f"timer.timer_device_{device_id}"

        if "hours" in slots:
            hours = int(slots["hours"]["value"])
        else:
            hours = 0

        if "minutes" in slots:
            minutes = int(slots["minutes"]["value"])
        else:
            minutes = 0

        if "seconds" in slots:
            seconds = int(slots["seconds"]["value"])
        else:
            seconds = 0

        duration = f"{hours:02}:{minutes:02}:{seconds:02}"

        timer_state = hass.states.get(entity_id)
        if timer_state is None:
            # Create timer entity for device
            component: EntityComponent[Timer] = hass.data[DOMAIN]
            timer = Timer(
                {
                    CONF_ID: f"device_{device_id}",
                    CONF_DURATION: duration,
                    CONF_RESTORE: False,
                }
            )
            timer.editable = False

            await component.async_add_entities([timer])
            _LOGGER.debug("Created timer entity: %s", timer.entity_id)

        async def handle_finished(event: Event) -> None:
            await async_device_timer_finished(hass, device_id)

        hass.bus.async_listen_once(EVENT_TIMER_FINISHED, handle_finished)

        _LOGGER.debug(
            "Starting timer with duration=%s, id=%s", duration, timer.entity_id
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_START,
            {
                CONF_ENTITY_ID: entity_id,
                CONF_DURATION: duration,
            },
            blocking=True,
        )

        timer_state = hass.states.get(timer.entity_id)
        assert timer_state is not None

        response = intent_obj.create_response()
        response.response_type = intent.IntentResponseType.ACTION_DONE
        response.async_set_states(matched_states=[timer_state])
        return response
