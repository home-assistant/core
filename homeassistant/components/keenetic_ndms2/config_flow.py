"""Config flow for Keenetic NDMS2."""
from __future__ import annotations

from urllib.parse import urlparse

from ndms2_client import Client, ConnectionException, InterfaceInfo, TelnetConnection
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INCLUDE_ARP,
    CONF_INCLUDE_ASSOCIATED,
    CONF_INTERFACES,
    CONF_TRY_HOTSPOT,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TELNET_PORT,
    DOMAIN,
    ROUTER,
)
from .router import KeeneticRouter


class KeeneticFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return KeeneticOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict = None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            _client = Client(
                TelnetConnection(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    timeout=10,
                )
            )

            try:
                router_info = await self.hass.async_add_executor_job(
                    _client.get_router_info
                )
            except ConnectionException:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=router_info.name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=self.context.get(CONF_HOST, vol.UNDEFINED)
                    ): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_TELNET_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict = None):
        """Import a config entry."""
        return await self.async_step_user(user_input)

    async def async_step_ssdp(self, discovery_info: dict):
        """Handle a discovered device."""
        # Filter out items not having "keenetic' in their name
        if (
            "keenetic"
            not in discovery_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME, "").lower()
        ):
            return self.async_abort(reason="not_keenetic_ndms2")

        # filters out items having no/empty UDN
        if not discovery_info.get(ssdp.ATTR_UPNP_UDN):
            return self.async_abort(reason="no_udn")

        host = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        unique_id = discovery_info[ssdp.ATTR_UPNP_UDN]

        self._async_abort_entries_match({CONF_HOST: host})

        await self.async_set_unique_id(unique_id)

        self.context[CONF_HOST] = host

        return await self.async_step_user()


class KeeneticOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self._interface_options = {}

    async def async_step_init(self, _user_input: dict = None):
        """Manage the options."""
        router: KeeneticRouter = self.hass.data[DOMAIN][self.config_entry.entry_id][
            ROUTER
        ]

        interfaces: list[InterfaceInfo] = await self.hass.async_add_executor_job(
            router.client.get_interfaces
        )

        self._interface_options = {
            interface.name: (interface.description or interface.name)
            for interface in interfaces
            if interface.type.lower() == "bridge"
        }
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict = None):
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): int,
                vol.Required(
                    CONF_CONSIDER_HOME,
                    default=self.config_entry.options.get(
                        CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME
                    ),
                ): int,
                vol.Required(
                    CONF_INTERFACES,
                    default=self.config_entry.options.get(
                        CONF_INTERFACES, [DEFAULT_INTERFACE]
                    ),
                ): cv.multi_select(self._interface_options),
                vol.Optional(
                    CONF_TRY_HOTSPOT,
                    default=self.config_entry.options.get(CONF_TRY_HOTSPOT, True),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_ARP,
                    default=self.config_entry.options.get(CONF_INCLUDE_ARP, True),
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_ASSOCIATED,
                    default=self.config_entry.options.get(
                        CONF_INCLUDE_ASSOCIATED, True
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=options)
