"""Config flow for ROMY integration."""
from __future__ import annotations

from typing import Any

import romy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_UUID
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER


def _schema_with_host() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST): cv.string,
        },
    )


def _schema_with_password() -> vol.Schema:
    return vol.Schema(
        {vol.Required(CONF_PASSWORD): vol.All(cv.string, vol.Length(8))},
    )


class RomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for ROMY."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Handle a config flow for ROMY."""
        self.romy_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        data = _schema_with_host()

        if user_input:
            self.romy_info[CONF_HOST] = user_input[CONF_HOST]

            new_romy = await romy.create_romy(self.romy_info[CONF_HOST], "")

            if not new_romy.is_initialized:
                errors[CONF_HOST] = "cannot_connect"

            # check if already setuped
            await self.async_set_unique_id(new_romy.unique_id)
            self._abort_if_unique_id_configured()

            self.romy_info[CONF_NAME] = new_romy.name

            if not new_romy.is_unlocked:
                return await self.async_step_unlock_http_interface()

            if not errors:
                return await self._async_step_finish_config()

        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_unlock_http_interface(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Unlock the http interface with password if robot is locked."""
        errors: dict[str, str] = {}
        data = _schema_with_password()

        if user_input:
            self.romy_info[CONF_PASSWORD] = user_input[CONF_PASSWORD]
            new_romy = await romy.create_romy(
                self.romy_info[CONF_HOST], self.romy_info[CONF_PASSWORD]
            )

            if not new_romy.is_initialized or not new_romy.is_unlocked:
                errors[CONF_PASSWORD] = "invalid_auth"

            if not errors:
                return await self._async_step_finish_config()

        return self.async_show_form(
            step_id="unlock_http_interface", data_schema=data, errors=errors
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # connect and gather information from your ROMY
        host = discovery_info.host
        LOGGER.debug("ZeroConf Host: %s", host)

        new_discovered_romy = await romy.create_romy(host, "")

        name = new_discovered_romy.name
        LOGGER.debug("ZeroConf Name: %s", name)

        # get unique id and stop discovery if robot is already added
        unique_id = new_discovered_romy.unique_id
        LOGGER.debug("ZeroConf Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {"name": f"{name} ({host} / {unique_id})"},
                "configuration_url": f"http://{host}:{new_discovered_romy.port}",
            }
        )

        self.romy_info[CONF_HOST] = host
        self.romy_info[CONF_NAME] = name
        self.romy_info[CONF_UUID] = unique_id

        # if robot is already unlocked add it directly
        if new_discovered_romy.is_initialized and new_discovered_romy.is_unlocked:
            return await self.async_step_zeroconf_confirm()

        return await self.async_step_unlock_http_interface()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    "name": self.romy_info[CONF_NAME],
                    "host": self.romy_info[CONF_HOST],
                },
            )
        return await self._async_step_finish_config()

    async def _async_step_finish_config(self) -> FlowResult:
        """Finish the configuration setup."""
        return self.async_create_entry(
            title=self.romy_info[CONF_NAME], data=self.romy_info
        )
