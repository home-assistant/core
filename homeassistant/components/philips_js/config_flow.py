"""Config flow for Philips TV integration."""
import logging
from typing import Any, Dict, Optional, TypedDict

from haphilipsjs import ConnectionFailure, PhilipsTV
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_API_VERSION, CONF_HOST

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class FlowUserDict(TypedDict):
    """Data for user step."""

    host: str
    api_version: int


async def validate_input(hass: core.HomeAssistant, data: FlowUserDict):
    """Validate the user input allows us to connect."""
    hub = PhilipsTV(data[CONF_HOST], data[CONF_API_VERSION])

    await hass.async_add_executor_job(hub.getSystem)

    if hub.system is None:
        raise ConnectionFailure

    return hub.system


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Philips TV."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _default = {}

    async def async_step_import(self, conf: Dict[str, Any]):
        """Import a configuration from config.yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == conf[CONF_HOST]:
                return self.async_abort(reason="already_configured")

        return await self.async_step_user(
            {
                CONF_HOST: conf[CONF_HOST],
                CONF_API_VERSION: conf[CONF_API_VERSION],
            }
        )

    async def async_step_user(self, user_input: Optional[FlowUserDict] = None):
        """Handle the initial step."""
        errors = {}
        if user_input:
            self._default = user_input
            try:
                system = await validate_input(self.hass, user_input)
            except ConnectionFailure:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(system["serialnumber"])
                self._abort_if_unique_id_configured(updates=user_input)

                data = {**user_input, "system": system}

                return self.async_create_entry(
                    title=f"{system['name']} ({system['serialnumber']})", data=data
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._default.get(CONF_HOST)): str,
                vol.Required(
                    CONF_API_VERSION, default=self._default.get(CONF_API_VERSION)
                ): vol.In([1, 6]),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
