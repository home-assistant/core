import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HIVISpeakerConfigFlow(ConfigFlow, domain=DOMAIN):
    """HIVI speaker configuration flow"""

    async def async_step_user(self, user_input=None):
        """User step - configure integration"""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="HiVi Speaker", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow"""
        return HIVISpeakerOptionsFlow(config_entry)


class HIVISpeakerOptionsFlow(config_entries.OptionsFlow):
    """Options flow - using confirmation switch"""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.open_num = 0

    async def async_step_init(self, user_input=None):
        """Initial step"""
        _LOGGER.debug("Entering initial step of options flow")
        self.open_num = 0
        if user_input is not None:
            if user_input.get("confirm_refresh"):
                # Trigger refresh
                await self.hass.services.async_call(
                    DOMAIN, "refresh_discovery", {}, blocking=False
                )

                # Show success page
                return await self.async_step_success()

            # User canceled, return
            return self.async_create_entry(title="", data={})

        # Show confirmation dialog
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm_refresh", default=True): bool,
                }
            ),
        )

    async def async_step_success(self, user_input=None):
        """Success page"""
        _LOGGER.debug("Displaying success page")
        if self.open_num == 0:
            self.open_num += 1
            return self.async_show_form(
                step_id="success",
                data_schema=vol.Schema({}),
            )
        return self.async_create_entry(title="", data={})
