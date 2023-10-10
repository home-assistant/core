"""Config flow for La Marzocco integration."""
import logging
from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from lmcloud.exceptions import AuthFail, RequestNotSuccessful

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEFAULT_CLIENT_ID,
    CONF_DEFAULT_CLIENT_SECRET,
    CONF_USE_WEBSOCKET,
    DEFAULT_PORT_CLOUD,
    DOMAIN,
)
from .lm_client import LaMarzoccoClient

_LOGGER = logging.getLogger(__name__)

LOGIN_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)

STEP_USER_DATA_SCHEMA = LOGIN_DATA_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)

STEP_REAUTH_DATA_SCHEMA = LOGIN_DATA_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID, default=CONF_DEFAULT_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET, default=CONF_DEFAULT_CLIENT_SECRET): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    try:
        lm = LaMarzoccoClient(hass, data)
        lm.client = await lm._connect(data)
        lm._machine_info = await lm._get_machine_info()

        if not lm.machine_info:
            raise CannotConnect

    except AuthFail:
        _LOGGER.error("Server rejected login credentials")
        raise InvalidAuth
    except RequestNotSuccessful:
        _LOGGER.error("Failed to connect to server")
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": lm.machine_name, **lm.machine_info}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    VERSION = 2

    def __init__(self):
        self._discovered = {}

    async def _try_create_entry(self, data):
        machine_info = await validate_input(self.hass, data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=machine_info["title"], data={**data, **machine_info}
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            # Config entry already exists, only one allowed.
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            data = user_input.copy()
            data |= self._discovered
            data[CONF_PORT] = DEFAULT_PORT_CLOUD
            data[CONF_CLIENT_ID] = CONF_DEFAULT_CLIENT_ID
            data[CONF_CLIENT_SECRET] = CONF_DEFAULT_CLIENT_SECRET

            try:
                return await self._try_create_entry(data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_bluetooth(self, discovery_info):
        address = discovery_info.address
        name = discovery_info.name

        _LOGGER.debug(f"Discovered La Marzocco machine {name} through Bluetooth at address {address}")

        self._discovered[CONF_NAME] = name
        self._discovered[CONF_MAC] = address

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_DATA_SCHEMA,
            )
        self.hass.config_entries.async_update_entry(
            self.reauth_entry, data=user_input
        )
        await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Manage the options for the custom component."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            if not errors:
                # write entry to config and not options dict, pass empty options out
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=user_input, options=self.config_entry.options
                )

                return self.async_create_entry(
                    title="",
                    data=user_input
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=self.config_entry.data.get(CONF_HOST)
                    ): cv.string,
                    vol.Required(
                        CONF_CLIENT_ID,
                        default=self.config_entry.data.get(CONF_CLIENT_ID)
                    ): cv.string,
                    vol.Required(
                        CONF_CLIENT_SECRET,
                        default=self.config_entry.data.get(CONF_CLIENT_SECRET)
                    ): cv.string,
                    vol.Required(
                        CONF_USERNAME,
                        default=self.config_entry.data.get(CONF_USERNAME)
                    ): cv.string,
                    vol.Required(
                        CONF_PASSWORD,
                        default=self.config_entry.data.get(CONF_PASSWORD)
                    ): cv.string,
                    vol.Optional(
                        CONF_USE_WEBSOCKET,
                        default=self.config_entry.options.get(CONF_USE_WEBSOCKET, True)
                    ): cv.boolean,
                }
            ),
            errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
