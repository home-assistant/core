"""Config flow for EPS integration."""
import logging

from pyepsalarm import EPS
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def _get_device_site(hass: core.HomeAssistant, token, username, password):
    eps_api = EPS(token, username, password)
    return await hass.async_add_executor_job(eps_api.get_site)


class EPSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EPS."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        site = None

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                # If we are able to get the site address, we are able to establish
                # a connection to the device.
                site = await _get_device_site(self.hass, token, username, password)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        if errors or (user_input is None):
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        await self.async_set_unique_id(site)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
