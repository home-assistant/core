"""Config flow for DayBetter light local."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import Any

from daybetter_local_api import DayBetterController

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_flow

from .const import (
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""


    adapter = await network.async_get_source_ip(hass, network.PUBLIC_TARGET_IP)


    controller = DayBetterController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_address=adapter,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISTENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    devices_found = False
    try:
        await controller.start()
        controller.send_discovery_message()

        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                while not controller.devices:
                    await asyncio.sleep(0.1)
        except TimeoutError:
            _LOGGER.debug("No DayBetter devices found during discovery")
            return False

        # Check if we found any devices that aren't already configured
        for device in controller.devices:
            unique_id = getattr(device, "fingerprint", None) or getattr(device, "ip", None)
            if unique_id:
                # Check if this device is already configured
                await hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
                    data={"unique_id": unique_id},
                )
                devices_found = True

    except OSError as ex:
        _LOGGER.error("Failed to start controller, errno: %d", ex.errno)
        return False
    finally:
        cleanup = controller.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup.wait(), 1)

    return devices_found


class DayBetterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for DayBetter."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Check if there are any devices available
        if not await self._async_discover_devices():
            return self.async_abort(reason="no_devices_found")

        # If we get here, devices were found, create the entry
        # For single device setups, we can create the entry directly
        # For multiple devices, we'd need to show a selection form
        return self.async_create_entry(title="DayBetter light local", data={})

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle integration discovery."""
        unique_id = discovery_info["unique_id"]

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def _async_discover_devices(self) -> bool:
        """Discover devices and check for unique IDs."""
        try:
            adapter = await network.async_get_source_ip(self.hass, network.PUBLIC_TARGET_IP)
        except (HomeAssistantError, ValueError, RuntimeError):
            adapter = "0.0.0.0"

        controller = DayBetterController(
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
            controller.send_discovery_message()

            try:
                async with asyncio.timeout(DISCOVERY_TIMEOUT):
                    while not controller.devices:
                        await asyncio.sleep(0.1)
            except TimeoutError:
                _LOGGER.debug("No DayBetter devices found during discovery")
                return False

            # Check each device and abort if already configured
            for device in controller.devices:
                unique_id = getattr(device, "fingerprint", None) or getattr(device, "ip", None)
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return True


        except OSError as ex:
            _LOGGER.error("Failed to start controller, errno: %d", ex.errno)
            return False
        finally:
            cleanup = controller.cleanup()
            with suppress(TimeoutError):
                await asyncio.wait_for(cleanup.wait(), 1)

        return False


# Register the discovery flow using the correct method
config_entry_flow.register_discovery_flow(
    DOMAIN, "DayBetter light local", _async_has_devices
)
