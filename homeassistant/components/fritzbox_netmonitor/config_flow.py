"""Config flow for fritzbox_netmonitor"""
from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

# pylint:disable=unused-import
from .const import CONF_DEFAULT_IP, DOMAIN

DATA_SCHEMA_USER = vol.Schema({vol.Optional(CONF_HOST, default=CONF_DEFAULT_IP): str})

RESULT_SUCCESS = "success"
RESULT_NOT_FOUND = "not_found"


class FritzboxNetMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a fritzbox_netmonitor config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize flow."""
        self._host = None

    def _get_entry(self):
        """Create and return an entry."""
        return self.async_create_entry(title=self._name, data={CONF_HOST: self._host},)

    def _try_connect(self):
        """Try to connect"""
        try:
            fritzbox_status = FritzStatus(address=self._host)
        except (ValueError, TypeError, FritzConnectionException):
            return RESULT_NOT_FOUND
        return RESULT_SUCCESS

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                    return self.async_abort(reason="already_configured")

            self._host = user_input[CONF_HOST]

            result = await self.hass.async_add_executor_job(self._try_connect)

            if result == RESULT_SUCCESS:
                return self._get_entry()
            elif result == RESULT_NOT_FOUND:
                return self.async_abort(reason=result)
            errors["base"] = result

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA_USER, errors=errors
        )
