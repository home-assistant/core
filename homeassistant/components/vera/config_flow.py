"""Config flow for Vera."""
import pyvera as pv
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import CONF_CONTROLLER, DOMAIN


class VeraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Vera config flow."""

    async def async_step_user(self, config: dict = None):
        """Handle user initiated flow."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        if config:
            return await self.async_step_finish(config)

        return self.async_show_form(
            step_id="setup",
            data_schema=vol.Schema({vol.Required(CONF_CONTROLLER): cv.url}),
        )

    async def async_step_import(self, config: dict):
        """Handle a flow initialized by import."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        return await self.async_step_finish(config)

    async def async_step_finish(self, config: dict):
        """Validate and create config entry."""
        base_url = config.get(CONF_CONTROLLER)

        try:
            controller = pv.VeraController(base_url)
            await self.hass.async_add_job(controller.refresh_data)
        except RequestException:
            return self.async_abort(
                reason="cannot_connect", description_placeholders={"base_url": base_url}
            )

        return self.async_create_entry(title=base_url, data=config)
