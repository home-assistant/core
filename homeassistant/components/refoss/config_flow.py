"""Config Flow for Refoss integration."""

from typing import Any, override

import probatio

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_NETWORKS, DISCOVERY_TIMEOUT, DOMAIN, LOGGER
from .probe import build_probe_addresses, networks_from_options, normalize_networks
from .util import refoss_discovery_server

NETWORKS_SELECTOR = selector.TextSelector(selector.TextSelectorConfig(multiline=True))


def _networks_schema(default: str) -> probatio.Schema:
    """Return the schema for the networks field."""
    return probatio.Schema(
        {probatio.Optional(CONF_NETWORKS, default=default): NETWORKS_SELECTOR}
    )


class RefossOptionsFlow(OptionsFlow):
    """Handle Refoss options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage extra discovery networks."""
        errors: dict[str, str] = {}
        networks_input = ", ".join(networks_from_options(self.config_entry.options))

        if user_input is not None:
            networks_input = user_input.get(CONF_NETWORKS, "")
            networks = normalize_networks(networks_input)
            if networks is None:
                errors[CONF_NETWORKS] = "invalid_networks"
            else:
                return self.async_create_entry(
                    title="", data={CONF_NETWORKS: networks} if networks else {}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_networks_schema(networks_input),
            errors=errors,
        )


class RefossConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Refoss config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RefossOptionsFlow:
        """Get the options flow for this handler."""
        return RefossOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        networks_input = ""

        if user_input is not None:
            networks_input = user_input.get(CONF_NETWORKS, "")
            networks = normalize_networks(networks_input)
            if networks is None:
                errors[CONF_NETWORKS] = "invalid_networks"
            else:
                if not await self._async_discover(networks):
                    return self.async_abort(reason="no_devices_found")
                return self.async_create_entry(
                    title="Refoss",
                    data={},
                    options={CONF_NETWORKS: networks} if networks else {},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_networks_schema(networks_input),
            errors=errors,
        )

    async def _async_discover(self, networks: list[str]) -> bool:
        """Return whether a probe found at least one device."""
        discovery = await refoss_discovery_server(self.hass)
        local_broadcasts = [
            str(address)
            for address in await async_get_ipv4_broadcast_addresses(self.hass)
        ]
        addresses = build_probe_addresses(
            networks,
            local_broadcasts=local_broadcasts,
            known_ips=(),
            include_hosts=any("/" in network for network in networks),
        )
        devices = await discovery.broadcast_msg(
            wait_for=DISCOVERY_TIMEOUT, addresses=addresses
        )

        LOGGER.debug(
            "Discovered devices: [%s]",
            ", ".join(info.dev_name for info in devices),
        )
        return len(devices) > 0
