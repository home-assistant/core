"""Config flow to configure ais wear os component."""

import asyncio
import logging

from homeassistant import config_entries
from homeassistant.components.ais_dom import ais_global

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
G_AIS_PIN_CHECK = 0


@config_entries.HANDLERS.register(DOMAIN)
class HostFlowHandler(config_entries.ConfigFlow):
    """AIS Wear OS config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(
            step_id="confirm",
            errors=errors,
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        global G_AIS_PIN_CHECK
        errors = {}
        if user_input is not None:
            # reset PIN
            G_AIS_PIN_CHECK = 0
            ais_global.G_AIS_DOM_PIN = ""
            await self.hass.services.async_call(
                "ais_cloud", "enable_gate_pairing_by_pin"
            )
            return await self.async_step_generate_pin(user_input=None)
        return self.async_show_form(
            step_id="init",
            errors=errors,
        )

    async def async_step_generate_pin(self, user_input=None):
        """Handle a flow start."""
        global G_AIS_PIN_CHECK
        errors = {}

        while len(ais_global.G_AIS_DOM_PIN) < 6 and G_AIS_PIN_CHECK < 10:
            await asyncio.sleep(1)
            G_AIS_PIN_CHECK += 1
            _LOGGER.error(" G_AIS_PIN_CHECK: " + str(G_AIS_PIN_CHECK))

        if len(ais_global.G_AIS_DOM_PIN) < 6:
            return self.async_abort(reason="pin_error")
        else:
            return self.async_show_form(
                step_id="enter_pin",
                errors=errors,
                description_placeholders={"pin_code": ais_global.G_AIS_DOM_PIN},
            )

    async def async_step_enter_pin(self, user_input=None):
        """Handle a flow start."""
        global G_AIS_PIN_CHECK
        errors = {}
        if user_input is not None:
            """Finish config flow"""
            return self.async_abort(reason="go_to_device")

        # wait for pin
        return self.async_show_form(
            step_id="enter_pin",
            errors=errors,
            description_placeholders={"pin_code": ais_global.G_AIS_DOM_PIN},
        )
