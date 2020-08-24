"""Config flow for Risco integration."""
import logging

from pyrisco import CannotConnectError, RiscoAPI, UnauthorizedError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CODE_ARM_REQUIRED,
    CONF_CODE_DISARM_REQUIRED,
    DEFAULT_SCAN_INTERVAL,
)
from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema({CONF_USERNAME: str, CONF_PASSWORD: str, CONF_PIN: str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    risco = RiscoAPI(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])

    try:
        await risco.login(async_get_clientsession(hass))
    finally:
        await risco.close()

    return {"title": risco.site_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Risco."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @core.callback
    def async_get_options_flow(config_entry):
        """Define the config flow to handle options."""
        return RiscoOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except UnauthorizedError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class RiscoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Risco options flow."""

    def __init__(self, config_entry):
        """Initialize."""
        self.config_entry = config_entry

    def _options_schema(self):
        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        code_arm_required = self.config_entry.options.get(CONF_CODE_ARM_REQUIRED, False)
        code_disarm_required = self.config_entry.options.get(
            CONF_CODE_DISARM_REQUIRED, False
        )

        return vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=scan_interval): int,
                vol.Required(CONF_CODE_ARM_REQUIRED, default=code_arm_required): bool,
                vol.Required(
                    CONF_CODE_DISARM_REQUIRED, default=code_disarm_required
                ): bool,
            }
        )

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self._options_schema())
