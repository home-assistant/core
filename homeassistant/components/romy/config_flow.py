"""Config flow for ROMY integration."""
from __future__ import annotations

import romy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER


def _schema_with_defaults(
    host: str = "", name: str = "", requires_password: bool = False
) -> vol.Schema:
    schema = {
        vol.Required(CONF_HOST, default=host): cv.string,
        vol.Optional(CONF_NAME, default=name): cv.string,
    }

    if requires_password:
        schema.update(
            {vol.Required(CONF_PASSWORD, default=""): vol.All(str, vol.Length(8))}
        )

    return vol.Schema(schema)


class RomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for ROMY."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Handle a config flow for ROMY."""
        self.discovery_schema = None
        self.host: str = ""
        self.name: str = ""
        self.password: str = ""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        data = self.discovery_schema or _schema_with_defaults()

        if user_input is not None:
            if not errors:
                ## Save the user input and finish the setup
                self.host = user_input["host"]
                self.name = user_input["name"]
                if "password" in user_input:
                    self.password = user_input["password"]

                new_romy = await romy.create_romy(self.host, self.password)

                if not new_romy.is_initialized:
                    errors[CONF_HOST] = "cannot_connect"

                if not new_romy.is_unlocked:
                    errors[CONF_PASSWORD] = "invalid_auth"

                if not errors:
                    return self.async_create_entry(
                        title=user_input["name"], data=user_input
                    )

        return self.async_show_form(step_id="user", data_schema=data, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""

        LOGGER.debug("Zeroconf discovery_info: %s", discovery_info)

        # extract unique id and stop discovery if robot is already added
        unique_id = discovery_info.hostname.split(".")[0]
        LOGGER.debug("Unique_id: %s", unique_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # get ROMY's name and check if local http interface is locked
        new_discovered_romy = await romy.create_romy(discovery_info.host, "")
        discovery_info.name = new_discovered_romy.name

        self.context.update(
            {
                "title_placeholders": {
                    "name": f"{unique_id.split('-')[1]} ({discovery_info.host})"
                },
                "configuration_url": f"http://{discovery_info.host}:{new_discovered_romy.port}",
            }
        )

        if new_discovered_romy.is_unlocked:
            self.discovery_schema = _schema_with_defaults(
                host=discovery_info.host,
                name=discovery_info.name,
            )
        else:
            self.discovery_schema = _schema_with_defaults_and_password(
                host=discovery_info.host,
                name=discovery_info.name,
                password="",
            )
        return await self.async_step_user()
