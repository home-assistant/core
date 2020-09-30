"""Config flow for NIU."""
import logging

from aiohttp import ClientError
from niu import NiuAPIException, NiuCloud, NiuNetException, NiuServerException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (  # pylint: disable=unused-import
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


@callback
def configured_instances(hass):
    """Return a set of configured Tesla instances."""
    return {entry.title for entry in hass.config_entries.async_entries(DOMAIN)}


class NiuConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow for NIU."""

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""

        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={},
                description_placeholders={},
            )

        if user_input[CONF_USERNAME] in configured_instances(self.hass):
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={CONF_USERNAME: "identifier_exists"},
                description_placeholders={},
            )

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        errors = {}
        try:
            token = await setup_account(self.hass, user_input)
        except NiuAPIException:
            errors["base"] = "invalid_credentials"
        except NiuServerException:
            errors["base"] = "server_error"
        except (NiuNetException, TimeoutError, ClientError):
            errors["base"] = "connection_error"

        if len(errors) > 0:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors=errors,
                description_placeholders={},
            )

        return self.async_create_entry(
            title=user_input[CONF_USERNAME],
            data={CONF_TOKEN: token},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for NIU."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


async def setup_account(hass, conf: dict):
    """Set up a NIU account."""

    account = NiuCloud(username=conf[CONF_USERNAME], password=conf[CONF_PASSWORD])

    return await account.connect()
