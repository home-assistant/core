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


def _schema_with_defaults(
    default_values: dict[str, Any] | None = None,
    requires_password: bool = False,
) -> vol.Schema:
    if default_values is None:
        default_values = {}
    schema = {
        vol.Required(CONF_HOST, default=default_values.get(CONF_HOST, "")): cv.string,
    }

    if requires_password:
        schema[vol.Required(CONF_PASSWORD)] = vol.All(str, vol.Length(8))

    return vol.Schema(schema)


class RomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for ROMY."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Handle a config flow for ROMY."""
        self.discovery_schema = None
        self.discovery_info: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        data = self.discovery_schema or _schema_with_defaults()

        if user_input:
            # Save the user input and finish the setup
            new_romy = await romy.create_romy(
                user_input[CONF_HOST], user_input.get(CONF_PASSWORD, "")
            )

            await self.async_set_unique_id(new_romy.unique_id)

            if not new_romy.is_initialized:
                errors[CONF_HOST] = "cannot_connect"

            if not new_romy.is_unlocked:
                data = _schema_with_defaults(user_input, requires_password=True)
                errors[CONF_PASSWORD] = "invalid_auth"

            if not errors:
                return self.async_create_entry(title=new_romy.name, data=user_input)

        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # get ROMY's name and check if local http interface is locked
        host = discovery_info.host
        LOGGER.debug("ZeroConf Host: %s", host)

        new_discovered_romy = await romy.create_romy(host, "")

        # get unique id and stop discovery if robot is already added
        unique_id = new_discovered_romy.unique_id
        LOGGER.debug("ZeroConf Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)

        name = new_discovered_romy.name
        LOGGER.debug("ZeroConf Name: %s", name)

        self.discovery_info.update(
            {
                CONF_HOST: host,
                CONF_NAME: name,
                CONF_UUID: unique_id,
            }
        )

        self._abort_if_unique_id_configured()

        self.context.update(
            {
                "title_placeholders": {"name": f"{name} ({host} / {unique_id})"},
                "configuration_url": f"http://{host}:{new_discovered_romy.port}",
            }
        )

        self.discovery_schema = _schema_with_defaults(
            {CONF_HOST: discovery_info.host},
            requires_password=not new_discovered_romy.is_unlocked,
        )

        # if robot is already unlocked add it directly
        if new_discovered_romy.is_initialized and new_discovered_romy.is_unlocked:
            return await self.async_step_zeroconf_confirm()

        return await self.async_step_user()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a confirmation flow initiated by zeroconf."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    "name": self.discovery_info[CONF_NAME],
                    "host": self.discovery_info[CONF_HOST],
                },
            )

        return self.async_create_entry(
            title=self.discovery_info[CONF_NAME],
            data=self.discovery_info,
        )
