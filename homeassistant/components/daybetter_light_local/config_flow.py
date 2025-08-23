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
        # 用户提交了表单
        host: str = user_input["host"]

        # 设置唯一ID并检查是否已配置
        await self.async_set_unique_id(f"{DOMAIN}_{host}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"DayBetter Light {host}",
            data={"host": host},
        )

    # 首次进入，尝试自动发现
    discovered = await self._async_discover_device()
    if discovered:
        # 发现设备，设置唯一ID并检查是否已配置
        await self.async_set_unique_id(f"{DOMAIN}_{discovered['host']}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"DayBetter Light {discovered['host']}",
            data=discovered,
        )

    # 没有发现设备，显示表单
    return self.async_show_form(
        step_id="user",
        data_schema=vol.Schema({vol.Required("host"): str}),
        errors=errors,
    )


async def _async_discover_device(self) -> dict[str, Any] | None:
    """Discover a DayBetter device and return its info."""
    try:
        adapter = await network.async_get_source_ip(self.hass, network.PUBLIC_TARGET_IP)
    except OSError:
        adapter = "0.0.0.0"

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

    discovered_device = None
    try:
        await controller.start()

        try:
            async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
                while not controller.devices:
                    await asyncio.sleep(0.1)
        except TimeoutError:
            _LOGGER.debug("No devices discovered")
        finally:
            device: DayBetterDevice | None = next(iter(controller.devices), None)
            if device:
                discovered_device = {
                    "device": device.fingerprint,
                    "sku": getattr(device, "sku", "unknown"),
                    "host": device.ip,
                }

    except OSError as ex:
        _LOGGER.error("Controller start failed, errno: %d", ex.errno)
    finally:
        cleanup_complete: asyncio.Event = controller.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

    return discovered_device
