"""Config flow for Acaia integration."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfo
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_IS_NEW_STYLE_SCALE, DOMAIN


class AcaiaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Acaia."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}
        self._reload: bool = False
        self._discovered: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_MAC])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Acaia", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self._discovered.get(CONF_NAME, "")
                    ): str,
                    vol.Required(
                        CONF_MAC,
                        default=self._discovered.get(CONF_MAC, ""),
                    ): str,
                    vol.Optional(CONF_IS_NEW_STYLE_SCALE, default=True): bool,
                }
            ),
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle a discovered Bluetooth device."""
        self._discovered[CONF_MAC] = discovery_info.address
        self._discovered[CONF_NAME] = discovery_info.name

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()
