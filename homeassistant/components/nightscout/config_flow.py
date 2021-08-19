"""Config flow for Nightscout integration."""
from asyncio import TimeoutError as AsyncIOTimeoutError
import logging

from aiohttp import ClientError, ClientResponseError
from py_nightscout import Api as NightscoutAPI
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_API_KEY, CONF_UNIT_OF_MEASUREMENT, CONF_URL
from homeassistant.core import callback

from .const import DOMAIN, MG_DL, MMOL_L
from .utils import hash_from_url

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema({vol.Required(CONF_URL): str, vol.Optional(CONF_API_KEY): str})


async def _validate_input(data):
    """Validate the user input allows us to connect."""
    url = data[CONF_URL]
    api_key = data.get(CONF_API_KEY)
    try:
        api = NightscoutAPI(url, api_secret=api_key)
        status = await api.get_server_status()
        if status.settings.get("authDefaultRoles") == "status-only":
            await api.get_sgvs()
    except ClientResponseError as error:
        raise InputValidationError("invalid_auth") from error
    except (ClientError, AsyncIOTimeoutError, OSError) as error:
        raise InputValidationError("cannot_connect") from error

    # Return info to be stored in the config entry.
    return {"title": status.name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nightscout."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            unique_id = hash_from_url(user_input[CONF_URL])
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            try:
                info = await _validate_input(user_input)
            except InputValidationError as error:
                errors["base"] = error.base
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return NightscoutOptionsFlowHandler(config_entry)


class NightscoutOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Nightscout."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UNIT_OF_MEASUREMENT,
                    default=self.config_entry.options.get(
                        CONF_UNIT_OF_MEASUREMENT, MG_DL
                    ),
                ): vol.In({MG_DL, MMOL_L}),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class InputValidationError(exceptions.HomeAssistantError):
    """Error to indicate we cannot proceed due to invalid input."""

    def __init__(self, base: str) -> None:
        """Initialize with error base."""
        super().__init__()
        self.base = base
