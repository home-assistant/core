"""Config flow for Vera."""
from requests.exceptions import RequestException

from homeassistant import config_entries

from .const import CONF_CONTROLLER, DOMAIN


class VeraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Vera config flow."""

    async def async_step_import(self, config: dict):
        """Handle a flow initialized by import."""
        base_url = config.get(CONF_CONTROLLER)

        controller = self.hass.data[DOMAIN].controller

        try:
            controller.refresh_data()
        except RequestException:
            return self.async_abort(
                reason="cannot-connect", description_placeholders={"base_url": base_url}
            )

        return self.async_create_entry(title=base_url, data=config)
