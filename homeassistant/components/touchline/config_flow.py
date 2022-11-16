"""Config flow for Roth Touchline."""
import ipaddress
import logging
import re

from pytouchline import PyTouchline
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


@callback
def touchline_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {
        entry.data[CONF_IP_ADDRESS]
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Roth Touchline."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        host = user_input[CONF_IP_ADDRESS]
        self._async_abort_entries_match({CONF_IP_ADDRESS: host})
        py_touchline = PyTouchline()
        number_of_devices = int(py_touchline.get_number_of_devices(host))

        if number_of_devices <= 0:
            errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title=user_input[CONF_IP_ADDRESS],
            data={
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
            },
        )
