"""Config flow for Somfy MyLink integration."""
import asyncio
from copy import deepcopy
import logging

from somfy_mylink_synergy import SomfyMyLinkSynergy
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_REVERSE,
    CONF_REVERSED_TARGET_IDS,
    CONF_SYSTEM_ID,
    CONF_TARGET_ID,
    CONF_TARGET_NAME,
    DEFAULT_PORT,
    DOMAIN,
    MYLINK_STATUS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from schema with values provided by the user.
    """
    somfy_mylink = SomfyMyLinkSynergy(
        data[CONF_SYSTEM_ID], data[CONF_HOST], data[CONF_PORT]
    )

    try:
        status_info = await somfy_mylink.status_info()
    except asyncio.TimeoutError as ex:
        raise CannotConnect from ex

    if not status_info or "error" in status_info:
        _LOGGER.debug("Auth error: %s", status_info)
        raise InvalidAuth

    return {"title": f"MyLink {data[CONF_HOST]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Somfy MyLink."""

    VERSION = 1

    def __init__(self):
        """Initialize the somfy_mylink flow."""
        self.host = None
        self.mac = None
        self.ip_address = None

    async def async_step_dhcp(self, discovery_info):
        """Handle dhcp discovery."""
        self._async_abort_entries_match({CONF_HOST: discovery_info[IP_ADDRESS]})

        formatted_mac = format_mac(discovery_info[MAC_ADDRESS])
        await self.async_set_unique_id(format_mac(formatted_mac))
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: discovery_info[IP_ADDRESS]}
        )
        self.host = discovery_info[HOSTNAME]
        self.mac = formatted_mac
        self.ip_address = discovery_info[IP_ADDRESS]
        self.context["title_placeholders"] = {"ip": self.ip_address, "mac": self.mac}
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.ip_address): str,
                    vol.Required(CONF_SYSTEM_ID): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for somfy_mylink."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.options = deepcopy(dict(config_entry.options))
        self._target_id = None

    @callback
    def _async_callback_targets(self):
        """Return the list of targets."""
        return self.hass.data[DOMAIN][self.config_entry.entry_id][MYLINK_STATUS][
            "result"
        ]

    @callback
    def _async_get_target_name(self, target_id) -> str:
        """Find the name of a target in the api data."""
        mylink_targets = self._async_callback_targets()
        for cover in mylink_targets:
            if cover["targetID"] == target_id:
                return cover["name"]
        raise KeyError

    async def async_step_init(self, user_input=None):
        """Handle options flow."""

        if self.config_entry.state != config_entries.ENTRY_STATE_LOADED:
            _LOGGER.error("MyLink must be connected to manage device options")
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            target_id = user_input.get(CONF_TARGET_ID)
            if target_id:
                return await self.async_step_target_config(None, target_id)

            return self.async_create_entry(title="", data=self.options)

        cover_dict = {None: None}
        mylink_targets = self._async_callback_targets()
        if mylink_targets:
            for cover in mylink_targets:
                cover_dict[cover["targetID"]] = cover["name"]

        data_schema = vol.Schema({vol.Optional(CONF_TARGET_ID): vol.In(cover_dict)})

        return self.async_show_form(step_id="init", data_schema=data_schema, errors={})

    async def async_step_target_config(self, user_input=None, target_id=None):
        """Handle options flow for target."""
        reversed_target_ids = self.options.setdefault(CONF_REVERSED_TARGET_IDS, {})

        if user_input is not None:
            if user_input[CONF_REVERSE] != reversed_target_ids.get(self._target_id):
                reversed_target_ids[self._target_id] = user_input[CONF_REVERSE]
            return await self.async_step_init()

        self._target_id = target_id

        return self.async_show_form(
            step_id="target_config",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_REVERSE,
                        default=reversed_target_ids.get(target_id, False),
                    ): bool
                }
            ),
            description_placeholders={
                CONF_TARGET_NAME: self._async_get_target_name(target_id),
            },
            errors={},
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
