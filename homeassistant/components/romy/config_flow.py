"""Config flow for ROMY integration."""
from __future__ import annotations

from typing import Any

import romy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
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
        vol.Optional(CONF_NAME, default=default_values.get(CONF_NAME, "")): cv.string,
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

            # get robots name in case none was provided
            if not user_input[CONF_NAME]:
                user_input["name"] = new_romy.name

            if not new_romy.is_initialized:
                errors[CONF_HOST] = "cannot_connect"

            if not new_romy.is_unlocked:
                data = _schema_with_defaults(user_input, requires_password=True)
                errors[CONF_PASSWORD] = "invalid_auth"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # get ROMY's name and check if local http interface is locked
        new_discovered_romy = await romy.create_romy(discovery_info.host, "")
        discovery_info.name = new_discovered_romy.name

        # get unique id and stop discovery if robot is already added
        unique_id = new_discovered_romy.unique_id
        LOGGER.debug("Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"{discovery_info.name} ({discovery_info.host} / {unique_id})"
                },
                "configuration_url": f"http://{discovery_info.host}:{new_discovered_romy.port}",
            }
        )

        self.discovery_schema = _schema_with_defaults(
            {CONF_HOST: discovery_info.host, CONF_NAME: discovery_info.name},
            requires_password=not new_discovered_romy.is_unlocked,
        )
        return await self.async_step_user()
