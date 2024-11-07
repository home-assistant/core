"""Config flow for acaia integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_MAC, CONF_NAME

from .const import CONF_IS_NEW_STYLE_SCALE, DOMAIN

MAC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
    }
)

SCALE_VERSION_SCHEMA = vol.Schema(
    {vol.Optional(CONF_IS_NEW_STYLE_SCALE, default=True): bool}
)


class AcaiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for acaia."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        if user_input is not None:
            if self.source != SOURCE_RECONFIGURE:
                await self.async_set_unique_id(user_input[CONF_MAC])
                self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="acaia",
                data={**self._discovered, **user_input},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=(
                MAC_SCHEMA.extend(SCALE_VERSION_SCHEMA)
                if not self._discovered
                else SCALE_VERSION_SCHEMA
            ),
        )

    async def async_step_bluetooth(self, discovery_info) -> ConfigFlowResult:
        """Handle a discovered Bluetooth device."""
        self._discovered[CONF_MAC] = discovery_info.address
        self._discovered[CONF_NAME] = discovery_info.name

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Perform reconfiguration of the config entry."""
        reconfigure_entry = self._get_reconfigure_entry()

        if not user_input:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_MAC,
                            default=reconfigure_entry.data[CONF_MAC],
                        ): str,
                        vol.Optional(
                            CONF_IS_NEW_STYLE_SCALE,
                            default=reconfigure_entry.data[CONF_IS_NEW_STYLE_SCALE],
                        ): str,
                    }
                ),
            )

        return await self.async_step_user({**reconfigure_entry.data, **user_input})
