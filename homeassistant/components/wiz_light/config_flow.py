"""Config flow for wiz_light."""
import logging

from pywizlight import wizlight
from pywizlight.exceptions import WizLightConnectionError, WizLightTimeOutError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import AbortFlow

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WiZ Light."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            bulb = wizlight(user_input[CONF_HOST])
            try:
                mac = await bulb.getMac()
            except WizLightTimeOutError:
                errors["base"] = "bulb_time_out"
            except ConnectionRefusedError:
                errors["base"] = "cannot_connect"
            except WizLightConnectionError:
                errors["base"] = "no_wiz_light"
            except AbortFlow:
                return self.async_abort(reason="single_instance_allowed")
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
