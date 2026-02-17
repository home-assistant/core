"""Config flow for the iNet Radio integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from inet_control import RadioManager
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MANUAL_ENTRY = "manual"
DISCOVERY_TIMEOUT = 3.0

STEP_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


class INetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iNet Radio."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_radios: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step with discovery."""
        if user_input is not None:
            selected = user_input.get("device", MANUAL_ENTRY)
            if selected == MANUAL_ENTRY:
                return await self.async_step_manual()
            return await self._async_validate_and_create(selected)

        # Discover radios on the network
        self._discovered_radios = await self._async_discover_radios()

        if not self._discovered_radios:
            return await self.async_step_manual()

        # Build selection options
        device_options = {
            ip: f"{name} ({ip})" for ip, name in self._discovered_radios.items()
        }
        device_options[MANUAL_ENTRY] = "Enter IP address manually"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("device"): vol.In(device_options)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry."""
        if user_input is not None:
            return await self._async_validate_and_create(user_input[CONF_HOST])

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
        )

    async def _async_validate_and_create(self, host: str) -> ConfigFlowResult:
        """Validate connection and create config entry."""
        errors: dict[str, str] = {}
        manager = RadioManager()
        try:
            await manager.start()
            radio = await manager.connect(host, timeout=5.0)
        except TimeoutError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception during connection")
            errors["base"] = "unknown"
        else:
            unique_id = radio.unique_id
            title = radio.name or f"iNet Radio ({host})"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host})

            return self.async_create_entry(
                title=title,
                data={CONF_HOST: host},
            )
        finally:
            await manager.stop()

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_SCHEMA,
            errors=errors,
        )

    async def _async_discover_radios(self) -> dict[str, str]:
        """Discover radios on the network using broadcast."""
        manager = RadioManager()
        try:
            await manager.start()
            await manager.discover()
            await asyncio.sleep(DISCOVERY_TIMEOUT)
        except OSError:
            _LOGGER.debug("Discovery failed", exc_info=True)
            return {}
        finally:
            await manager.stop()

        return {ip: radio.name for ip, radio in manager.radios.items()}
