"""Config flow for Govee Local API."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BIND_ADDRESS,
    CONF_DISCOVERY_INTERVAL,
    CONF_DISCOVERY_INTERVAL_DEFAULT,
    CONF_LISENING_PORT,
    CONF_LISENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT,
    CONF_TARGET_PORT_DEFAULT,
    DOMAIN,
)

CONFIG_SCHEMA_ADVANCED = {
    vol.Required(
        CONF_MULTICAST_ADDRESS,
        default=CONF_MULTICAST_ADDRESS_DEFAULT,
    ): cv.string,
    vol.Required(CONF_LISENING_PORT, default=CONF_LISENING_PORT_DEFAULT): cv.port,
    vol.Required(CONF_TARGET_PORT, default=CONF_TARGET_PORT_DEFAULT): cv.port,
}


_LOGGING = logging.getLogger(__name__)


class GoveeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Govee Local API config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return GoveeOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step during setup."""
        if not user_input:
            adapter = await network.async_get_source_ip(
                self.hass, network.MDNS_TARGET_IP
            )

            data_schema = {
                vol.Required("bind_address", default=adapter): str,
                vol.Required(
                    CONF_DISCOVERY_INTERVAL, default=CONF_DISCOVERY_INTERVAL_DEFAULT
                ): vol.All(int, vol.Range(min=30, max=3600)),
            }
            if self.show_advanced_options:
                data_schema.update(CONFIG_SCHEMA_ADVANCED)

            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )

        if CONF_MULTICAST_ADDRESS not in user_input:
            user_input[CONF_MULTICAST_ADDRESS] = CONF_MULTICAST_ADDRESS_DEFAULT
        if CONF_LISENING_PORT not in user_input:
            user_input[CONF_LISENING_PORT] = CONF_LISENING_PORT_DEFAULT
        if CONF_TARGET_PORT not in user_input:
            user_input[CONF_TARGET_PORT] = CONF_TARGET_PORT_DEFAULT

        await self.async_set_unique_id(self._get_unique_id_for_controller(user_input))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"govee@{user_input[CONF_BIND_ADDRESS]}", data={"config": user_input}
        )

    def _get_unique_id_for_controller(self, config: dict[str, Any]) -> str:
        return "GoveeLocalApi:{}:{}:{}:{}".format(
            config[CONF_BIND_ADDRESS],
            config[CONF_LISENING_PORT],
            config[CONF_MULTICAST_ADDRESS],
            config[CONF_TARGET_PORT],
        )


class GoveeOptionsFlowHandler(OptionsFlow):
    """Handle options for Govee Local Api."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if not user_input:
            old_update_interval = self.config_entry.options.get(
                CONF_DISCOVERY_INTERVAL, CONF_DISCOVERY_INTERVAL_DEFAULT
            )
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_DISCOVERY_INTERVAL, default=old_update_interval
                        ): vol.All(int, vol.Range(min=30, max=3600))
                    }
                ),
            )

        return self.async_create_entry(title=self.config_entry.title, data=user_input)
