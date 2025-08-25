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
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _async_discover_devices(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Discover DayBetter devices and return a list of device info dicts."""

    try:
        adapter = await network.async_get_source_ip(hass, network.PUBLIC_TARGET_IP)
    except (HomeAssistantError, ValueError, RuntimeError):
        adapter = "0.0.0.0"

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

    discovered_devices = []

    try:
        await controller.start()
        controller.send_discovery_message()

        try:
            async with asyncio.timeout(DISCOVERY_TIMEOUT):
                while not controller.devices:
                    await asyncio.sleep(0.1)
        except TimeoutError:
            _LOGGER.debug("No DayBetter devices found during discovery")

        # 使用正确的设备属性
        discovered_devices = [
            {
                "fingerprint": getattr(device, "fingerprint", ""),
                "ip": getattr(device, "ip", ""),
                "sku": getattr(device, "sku", "Unknown"),
                "name": f"DayBetter {getattr(device, 'sku', 'Light')}",
            }
            for device in controller.devices
        ]

    except OSError as ex:
        _LOGGER.error("Failed to start DayBetter controller, errno: %d", ex.errno)
        if ex.errno == EADDRINUSE:
            _LOGGER.error("Port %d already in use", CONF_LISTENING_PORT_DEFAULT)
    finally:
        # cleanup controller
        cleanup_complete = controller.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup_complete.wait(), 1)

    return discovered_devices


class DayBetterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter light local."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_devices: list[dict[str, Any]] = []
        self.selected_device: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if "device" in user_input:
                # 用户选择了发现的设备
                device_index = int(user_input["device"])
                self.selected_device = self.discovered_devices[device_index]

                await self.async_set_unique_id(self.selected_device["fingerprint"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self.selected_device["name"],
                    data={"host": self.selected_device["ip"]},
                )
            # 用户选择手动输入
            return await self.async_step_manual()

        # 尝试自动发现设备
        self.discovered_devices = await _async_discover_devices(self.hass)

        if not self.discovered_devices:
            # 没有发现设备，转到手动输入
            return await self.async_step_manual()

        # 显示设备选择表单
        device_options = {
            str(i): device["name"] for i, device in enumerate(self.discovered_devices)
        }
        device_options["manual"] = "Manually enter the IP address"

        # 修复：确保 schema 包含 device 字段
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("device"): vol.In(device_options)}),
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP address input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input["host"]

            if not host or host.strip() == "":
                errors["base"] = "invalid_host"
            else:
                # 验证连接
                try:
                    controller = DayBetterController(
                        loop=self.hass.loop,
                        logger=_LOGGER,
                        listening_address=host,
                        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
                        broadcast_port=CONF_TARGET_PORT_DEFAULT,
                        listening_port=CONF_LISTENING_PORT_DEFAULT,
                        discovery_enabled=True,
                        discovery_interval=1,
                        update_enabled=False,
                    )

                    await controller.start()
                    controller.send_discovery_message()
                    await asyncio.sleep(1)  # 等待发现

                    if not controller.devices:
                        errors["base"] = "no_devices_found"
                    else:
                        # 使用发现的第一个设备
                        device = controller.devices[0]
                        unique_id = getattr(device, "fingerprint", host)

                        await self.async_set_unique_id(unique_id)
                        self._abort_if_unique_id_configured()

                        cleanup_complete = controller.cleanup()
                        with suppress(TimeoutError):
                            await asyncio.wait_for(cleanup_complete.wait(), 1)

                        return self.async_create_entry(
                            title=f"DayBetter Light {host}",
                            data={"host": host},
                        )

                except OSError as ex:
                    if ex.errno == EADDRINUSE:
                        errors["base"] = "address_in_use"
                    else:
                        errors["base"] = "connection_failed"

                finally:
                    if "controller" in locals():
                        cleanup_complete = controller.cleanup()
                        with suppress(TimeoutError):
                            await asyncio.wait_for(cleanup_complete.wait(), 1)

        # 修复：确保 schema 包含 host 字段
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str  # 确保这里定义了 host 字段
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml."""
        # 这里可以实现从YAML导入的逻辑
        # 暂时直接转到用户步骤
        return await self.async_step_user(user_input)
