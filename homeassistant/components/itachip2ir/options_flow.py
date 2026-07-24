"""Options flow for Global Caché iTach IP2IR."""

import time
from typing import Any

from pyitach import (
    ItachClient,
    ItachConnectionError,
    ItachError,
    async_get_ir_capability,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

SOURCE_REFRESH_INFRARED_PORTS = "refresh_infrared_ports"
CONF_LAST_PORT_REFRESH = "last_port_refresh"


class ItachOptionsFlow(config_entries.OptionsFlow):
    """Handle options for iTach IP2IR."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options menu."""
        source = self.context.get("source")

        if source == SOURCE_REFRESH_INFRARED_PORTS:
            return await self.async_step_refresh_infrared_ports()

        return self.async_show_menu(
            step_id="init",
            menu_options=[SOURCE_REFRESH_INFRARED_PORTS],
        )

    async def async_step_refresh_infrared_ports(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Query the iTach and reload entities from current port configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._validate_current_infrared_ports()
            except ItachConnectionError:
                errors["base"] = "cannot_connect"
            except ItachError:
                errors["base"] = "unknown"
            except ValueError:
                errors["base"] = "no_ir_ports"
            else:
                return self._create_options_entry(force_reload=True)

        return self.async_show_form(
            step_id="refresh_infrared_ports",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def _validate_current_infrared_ports(self) -> None:
        """Validate current device port configuration has at least one IR port.

        Creating the options entry after this validation triggers the entry update
        listener and reloads the integration. The reload re-queries the device and
        rebuilds infrared entities from the current port configuration.
        """
        host = str(
            self._config_entry.options.get("host", self._config_entry.data["host"])
        )
        port = int(
            self._config_entry.options.get("port", self._config_entry.data["port"])
        )
        client = ItachClient(host, port)

        try:
            ir_capability = await async_get_ir_capability(client)
            if not ir_capability.enabled_ports:
                raise ValueError("No iTach IR output ports are currently available")
        finally:
            await client.close()

    @callback
    def _create_options_entry(
        self,
        *,
        force_reload: bool = False,
    ) -> config_entries.ConfigFlowResult:
        """Create the options entry preserving unrelated options."""
        options = dict(self._config_entry.options)
        if force_reload:
            options[CONF_LAST_PORT_REFRESH] = time.time()
        return self.async_create_entry(title="", data=options)
