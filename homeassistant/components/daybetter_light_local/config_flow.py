"""Config flow for DayBetter light local."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import Any

from daybetter_local_api import DayBetterController, DayBetterDevice
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DayBetterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter light local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host: str = user_input["host"]
            device_id: str = user_input.get("device", host)
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"DayBetter Light {host}",
                data=user_input,
            )

        discovered = await self._async_discover_device()
        if discovered:
            await self.async_set_unique_id(discovered["device"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"DayBetter Light {discovered['host']}",
                data=discovered,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): str}),
            errors=errors,
        )

    async def _async_discover_device(self) -> dict[str, Any] | None:
        """Discover a DayBetter device and return its info."""
        adapter = await network.async_get_source_ip(self.hass, network.PUBLIC_TARGET_IP)
        controller: DayBetterController = DayBetterController(
            loop=self.hass.loop,
            logger=_LOGGER,
            listening_address=adapter,
            broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
            broadcast_port=CONF_TARGET_PORT_DEFAULT,
            listening_port=CONF_LISTENING_PORT_DEFAULT,
            discovery_enabled=True,
            discovery_interval=1,
            update_enabled=False,
        )

        try:
            await controller.start()
        except OSError as ex:
            _LOGGER.error("Controller start failed, errno: %d", ex.errno)
            return None

        try:
            async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
                while not controller.devices:
                    await asyncio.sleep(delay=1)
        except TimeoutError:
            _LOGGER.debug("No devices discovered")
            return None

        device: DayBetterDevice | None = next(iter(controller.devices), None)
        if not device:
            return None

        cleanup_complete: asyncio.Event = controller.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

        return {
            "device": device,
            "sku": getattr(device, "sku", "unknown"),
            "host": device.ip,
        }
