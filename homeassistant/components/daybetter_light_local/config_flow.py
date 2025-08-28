"""Config flow for DayBetter light local."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging
from typing import Any

from daybetter_local_api import DayBetterController
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import (
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _async_discover_devices(
    hass: HomeAssistant, host: str | None = None
) -> list[dict[str, Any]] | str:
    """Discover DayBetter devices. If host is given, probe only that host."""

    adapter = await network.async_get_source_ip(hass, network.PUBLIC_TARGET_IP)

    controller = DayBetterController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_address=host if host else adapter,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISTENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    devices: list[dict[str, Any]] = []
    try:
        await controller.start()
        controller.send_discovery_message()

        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                while not controller.devices:
                    await asyncio.sleep(0.1)
        except TimeoutError:
            _LOGGER.debug("No DayBetter devices found during discovery")

        devices = [
            {
                "fingerprint": getattr(d, "fingerprint", host or ""),
                "ip": getattr(d, "ip", host or ""),
                "sku": getattr(d, "sku", "Unknown"),
                "name": f"DayBetter {getattr(d, 'sku', 'Light')}",
            }
            for d in controller.devices
        ]

    except OSError as ex:
        _LOGGER.error("Failed to start controller, errno: %d", ex.errno)
        if ex.errno == EADDRINUSE:
            return "address_in_use"  # 👈 特殊返回
    finally:
        cleanup = controller.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup.wait(), 1)

    return devices


class DayBetterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for DayBetter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the DayBetter config flow."""
        self.discovered_devices: list[dict[str, Any]] = []
        self.discovery_error: str | None = None  # 允许 str 或 None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle initial step."""
        if user_input is not None:
            if user_input["host"] == "manual":
                return await self.async_step_manual()
            return await self._async_create_entry_from_discovery(user_input["host"])

        # try discovery
        devices_or_error = await _async_discover_devices(self.hass)
        if isinstance(devices_or_error, str):
            self.discovered_devices = []
            self.discovery_error = devices_or_error
        else:
            self.discovered_devices = devices_or_error
            self.discovery_error = None

        if not self.discovered_devices:
            return await self.async_step_manual()

        # build device choices
        device_options = {
            dev["fingerprint"]: f"{dev['name']} ({dev['ip']})"
            for dev in self.discovered_devices
        }
        device_options["manual"] = "Manually enter IP address"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): vol.In(device_options)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input["host"].strip()
            devices_or_error = await _async_discover_devices(self.hass, host)

            if isinstance(devices_or_error, str):
                # 错误情况：address_in_use
                errors["base"] = devices_or_error
            else:
                devices: list[dict[str, Any]] = devices_or_error
                if not devices:
                    errors["base"] = "no_devices_found"
                else:
                    device = devices[0]
                    unique_id = str(device.get("fingerprint") or host)
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=str(device.get("name", host)),
                        data={"host": host},
                    )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required("host"): str}),
            errors=errors,
        )

    async def _async_create_entry_from_discovery(
        self, fingerprint: str
    ) -> ConfigFlowResult:
        """Create entry from discovered device fingerprint."""
        device = next(
            dev for dev in self.discovered_devices if dev["fingerprint"] == fingerprint
        )

        await self.async_set_unique_id(device["fingerprint"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=device["name"],
            data={"host": device["ip"]},  # 用用户输入的，而不是 device.ip
        )
