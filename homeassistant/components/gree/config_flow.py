"""Config flow for Gree."""

from ipaddress import IPv4Address
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import CONF_KNOWN_HOSTS, DOMAIN

KNOWN_HOSTS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_KNOWN_HOSTS): SelectSelector(
            SelectSelectorConfig(custom_value=True, options=[], multiple=True)
        )
    }
)


class GreeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> GreeOptionsFlow:
        """Get the options flow for this handler."""
        return GreeOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return await self.async_step_config()

    async def async_step_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure optional IPv4 discovery hints."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                known_hosts = _normalize_known_hosts(
                    user_input.get(CONF_KNOWN_HOSTS, [])
                )
            except ValueError:
                errors[CONF_KNOWN_HOSTS] = "invalid_host"
            else:
                return self.async_create_entry(
                    title="Gree Climate",
                    data={CONF_KNOWN_HOSTS: known_hosts},
                )

        return self.async_show_form(
            step_id="config", data_schema=KNOWN_HOSTS_SCHEMA, errors=errors
        )


class GreeOptionsFlow(OptionsFlow):
    """Handle Gree options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure optional IPv4 discovery hints."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                known_hosts = _normalize_known_hosts(
                    user_input.get(CONF_KNOWN_HOSTS, [])
                )
            except ValueError:
                errors[CONF_KNOWN_HOSTS] = "invalid_host"
            else:
                updated_data = dict(self.config_entry.data)
                updated_data[CONF_KNOWN_HOSTS] = known_hosts
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=updated_data
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                KNOWN_HOSTS_SCHEMA, self.config_entry.data
            ),
            errors=errors,
            last_step=True,
        )


def _normalize_known_hosts(hosts: list[str]) -> list[str]:
    """Trim and validate optional IPv4 discovery hints."""
    return [str(IPv4Address(address)) for host in hosts if (address := host.strip())]
