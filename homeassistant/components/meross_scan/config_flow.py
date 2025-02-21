"""Config Flow for meross_scan integration."""

from __future__ import annotations

from typing import Any

from meross_ha.discovery import Discovery
from meross_ha.exceptions import SocketError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MAC

from .const import _LOGGER, DISCOVERY_TIMEOUT, DOMAIN


class MerossConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for meross_scan."""

    VERSION = 1
    MINOR_VERSION = 1

    host: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self._handle_step(user_input, step_id="user")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        self.host = reconfigure_entry.data[CONF_HOST]
        return await self._handle_step(
            user_input,
            step_id="reconfigure",
            default_host=self.host,
            description_placeholders={"device_name": reconfigure_entry.title},
        )

    async def _handle_step(
        self,
        user_input: dict[str, Any] | None = None,
        step_id: str = "user",
        default_host: str = "",
        description_placeholders: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            device = await start_scan_device(host=host)
            if not device:
                errors["base"] = "no_devices_found"
            else:
                if mac := device[CONF_MAC]:
                    await self.async_set_unique_id(mac)
                    if step_id == "user":
                        self._abort_if_unique_id_configured({CONF_HOST: host})
                        return self.async_create_entry(
                            title=device["devName"],
                            data={CONF_HOST: host, "device": device},
                        )
                    if step_id == "reconfigure":
                        self._abort_if_unique_id_mismatch(reason="another_device")
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            data_updates={CONF_HOST: host, "device": device},
                        )
                errors["base"] = "firmware_not_fully_supported"

        schema = vol.Schema({vol.Required(CONF_HOST, default=default_host): str})
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            description_placeholders=description_placeholders,
            errors=errors,
        )


async def start_scan_device(host: str) -> dict | None:
    """Scan device on the host."""
    device = None
    discovery_server = Discovery()
    try:
        await discovery_server.initialize()
        device = await discovery_server.broadcast_msg(
            ip=host, wait_for=DISCOVERY_TIMEOUT
        )
    except SocketError:
        _LOGGER.debug(f"Failed socket scan on {host}")
    finally:
        discovery_server.closeDiscovery()
    return device
