"""Config flow for La Marzocco integration."""
from collections.abc import Mapping
import logging
from typing import Any

from lmcloud.exceptions import AuthFail, RequestNotSuccessful
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
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
        vol.Required(CONF_CLIENT_ID, default=DEFAULT_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET, default=DEFAULT_CLIENT_SECRET): cv.string,
    },
    extra=vol.PREVENT_EXTRA,
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect."""

    try:
        lm = LaMarzoccoClient(hass, data)
        machine_info = await lm.try_connect(data)

        if not machine_info:
            raise CannotConnect

    except AuthFail:
        _LOGGER.error("Server rejected login credentials")
        raise InvalidAuth
    except RequestNotSuccessful:
        _LOGGER.error("Failed to connect to server")
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": machine_info["machine_name"], **machine_info}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    VERSION = 2

    def __init__(self) -> None:
        """Init config flow."""
        self._discovered: dict[str, str] = {}
        self.reauth_entry: ConfigEntry | None

    async def _try_create_entry(self, data):
        """Try to create an entry."""
        machine_info = await validate_input(self.hass, data)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=machine_info["title"], data={**data, **machine_info}
        )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            # Config entry already exists, only one allowed.
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            data = user_input.copy()
            data |= self._discovered
            data[CONF_PORT] = DEFAULT_PORT_CLOUD
            data[CONF_CLIENT_ID] = DEFAULT_CLIENT_ID
            data[CONF_CLIENT_SECRET] = DEFAULT_CLIENT_SECRET

            try:
                return await self._try_create_entry(data)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by discovery over Bluetooth."""
        address = discovery_info.address
        name = discovery_info.name

        _LOGGER.debug(
            "Discovered La Marzocco machine %s through Bluetooth at address %s",
            name,
            address,
        )

        self._discovered[CONF_NAME] = name
        self._discovered[CONF_MAC] = address

        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        assert self.reauth_entry
        if user_input is not None:
            try:
                await validate_input(self.hass, self.reauth_entry.data | user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
