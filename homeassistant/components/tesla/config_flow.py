"""Tesla Config Flow."""
from collections import OrderedDict, defaultdict
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

DOMAIN = "tesla"

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return a set of configured Tesla instances."""
    return set(entry.title for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class TeslaFlowHandler(config_entries.ConfigFlow):
    """Handle a Tesla config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.login = None
        self.config = OrderedDict()
        self.data_schema = OrderedDict(
            [
                (vol.Required(CONF_USERNAME), str),
                (vol.Required(CONF_PASSWORD), str),
                (
                    vol.Optional(CONF_SCAN_INTERVAL, default=300),
                    vol.All(cv.positive_int, vol.Clamp(min=300)),
                ),
            ]
        )

    async def _show_form(
        self, step="user", placeholders=None, errors=None, data_schema=None
    ) -> None:
        """Show the form to the user."""
        _LOGGER.debug("show_form %s %s %s %s", step, placeholders, errors, data_schema)
        data_schema = data_schema or vol.Schema(self.data_schema)
        if step == "user":
            return self.async_show_form(
                step_id=step,
                data_schema=data_schema,
                errors=errors if errors else {},
                description_placeholders=placeholders if placeholders else {},
            )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        from teslajsonpy import Controller as teslaAPI, TeslaException

        if not user_input:
            return await self._show_form(data_schema=vol.Schema(self.data_schema))

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return await self._show_form(errors={CONF_USERNAME: "identifier_exists"})

        self.config[CONF_USERNAME] = user_input[CONF_USERNAME]
        self.config[CONF_PASSWORD] = user_input[CONF_PASSWORD]
        from datetime import timedelta

        self.config[CONF_SCAN_INTERVAL] = (
            user_input[CONF_SCAN_INTERVAL]
            if not isinstance(user_input[CONF_SCAN_INTERVAL], timedelta)
            else user_input[CONF_SCAN_INTERVAL].total_seconds()
        )

        try:
            controller = teslaAPI(
                self.config[CONF_USERNAME],
                self.config[CONF_PASSWORD],
                self.config[CONF_SCAN_INTERVAL],
            )
            self.hass.data[DOMAIN] = {
                "controller": controller,
                "devices": defaultdict(list),
            }
            _LOGGER.debug("Connected to the Tesla API.")
            return self.async_create_entry(
                title=self.config[CONF_USERNAME], data=self.config
            )
        except TeslaException as ex:
            if ex.code == 401:
                return await self._show_form(errors={"base": "invalid_credentials"})
            _LOGGER.error("Unable to communicate with Tesla API: %s", ex.message)
            return await self._show_form(
                errors={"base": "connection_error"},
                placeholders={"message": f"\n> {ex.message}"},
            )
        except BaseException as ex:
            _LOGGER.warning("Unknown error: %s", ex)
            return await self._show_form(errors={"base": "unknown_error"})
