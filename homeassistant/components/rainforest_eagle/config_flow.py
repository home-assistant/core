"""Config flow for Rainforest Eagle."""
from .sensor import hwtest

from homeassistant import config_entries
from .const import DOMAIN

from collections import OrderedDict
import voluptuous as vol

# import homeassistant.helpers.config_validation as cv

from homeassistant.const import CONF_IP_ADDRESS
from .const import CONF_CLOUD_ID, CONF_INSTALL_CODE


# #BLOCK: Inactive code due to zeroconf not being supported
# from homeassistant.helpers import config_entry_flow
# async def _async_has_devices(hass) -> bool:
#    """Return if there are devices that can be discovered."""
#    # TODO Check if there are any devices that can be discovered in the network.
#    devices = await hass.async_add_executor_job(my_pypi_dependency.discover)
#    return len(devices) > 0
#
# config_entry_flow.register_discovery_flow(
#    DOMAIN, "Rainforest Eagle", _async_has_devices, config_entries.CONN_CLASS_UNKNOWN


fields = OrderedDict()

fields[vol.Required(CONF_IP_ADDRESS)] = str
fields[vol.Required(CONF_CLOUD_ID)] = str  # cv.matches_regex(r"[0-9a-f]{6}")
fields[vol.Required(CONF_INSTALL_CODE)] = str  # cv.matches_regex(r"[0-9a-f]{16}")


@config_entries.HANDLERS.register(DOMAIN)
class EagleConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Step for user-initiated configuration."""
        errors = {}
        if user_input is not None:
            eag = await hwtest(
                user_input[CONF_CLOUD_ID],
                user_input[CONF_INSTALL_CODE],
                user_input[CONF_IP_ADDRESS],
            )
            if eag is not False:
                return self.async_create_entry(
                    title=user_input[CONF_CLOUD_ID], data=user_input
                )
            else:
                errors["base"] = "no_eagle"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )
