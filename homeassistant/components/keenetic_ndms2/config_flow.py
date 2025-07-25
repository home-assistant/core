"""Config flow for Keenetic NDMS2."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

from ndms2_client import Client, ConnectionException, InterfaceInfo, TelnetConnection
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)
from homeassistant.helpers.typing import VolDictType

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
)
from .router import KeeneticConfigEntry


class KeeneticFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    _host: str | bytes | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: KeeneticConfigEntry,
    ) -> KeeneticOptionsFlowHandler:
        """Get the options flow for this handler."""
        return KeeneticOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            host = self._host or user_input[CONF_HOST]
            if self.source != SOURCE_RECONFIGURE:
                self._async_abort_entries_match({CONF_HOST: host})

            _client = Client(
                TelnetConnection(
                    host,
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
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data={CONF_HOST: host, **user_input},
                    )
                return self.async_create_entry(
                    title=router_info.name, data={CONF_HOST: host, **user_input}
                )

        host_schema: VolDictType = (
            {vol.Required(CONF_HOST): str} if not self._host else {}
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    **host_schema,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_TELNET_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        existing_entry_data = dict(self._get_reconfigure_entry().data)
        self._host = existing_entry_data[CONF_HOST]

        return await self.async_step_user(user_input)

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle a discovered device."""
        friendly_name = discovery_info.upnp.get(ATTR_UPNP_FRIENDLY_NAME, "")

        # Filter out items not having "keenetic" in their name
        if "keenetic" not in friendly_name.lower():
            return self.async_abort(reason="not_keenetic_ndms2")

        # Filters out items having no/empty UDN
        if not discovery_info.upnp.get(ATTR_UPNP_UDN):
            return self.async_abort(reason="no_udn")

        # We can cast the hostname to str because the ssdp_location is not bytes and
        # not a relative url
        host = cast(str, urlparse(discovery_info.ssdp_location).hostname)
        await self.async_set_unique_id(discovery_info.upnp[ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._async_abort_entries_match({CONF_HOST: host})

        self._host = host
        self.context["title_placeholders"] = {
            "name": friendly_name,
            "host": host,
        }

        return await self.async_step_user()


class KeeneticOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options."""

    config_entry: KeeneticConfigEntry

    def __init__(self) -> None:
        """Initialize options flow."""
        self._interface_options: dict[str, str] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if (
            not hasattr(self.config_entry, "runtime_data")
            or not self.config_entry.runtime_data
        ):
            return self.async_abort(reason="not_initialized")

        router = self.config_entry.runtime_data

        try:
            interfaces: list[InterfaceInfo] = await self.hass.async_add_executor_job(
                router.client.get_interfaces
            )
        except ConnectionException:
            return self.async_abort(reason="cannot_connect")

        self._interface_options = {
            interface.name: (interface.description or interface.name)
            for interface in interfaces
            if interface.type.lower() == "bridge"
        }

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
                    default=[
                        item
                        for item in self.config_entry.options.get(
                            CONF_INTERFACES, [DEFAULT_INTERFACE]
                        )
                        if item in self._interface_options
                    ],
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
