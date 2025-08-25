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
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class DayBetterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DayBetter light local."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_devices: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # 用户提交了表单
            host: str = user_input["host"]

            # 验证主机地址
            if not host or host.strip() == "":
                errors["base"] = "invalid_host"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Required("host"): str}),
                    errors=errors,
                )

            # 设置唯一ID并检查是否已配置
            unique_id = f"{DOMAIN}_{host}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # 测试连接
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
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema({vol.Required("host"): str}),
                        errors=errors,
                    )

                cleanup_complete = controller.cleanup()
                with suppress(TimeoutError):
                    await asyncio.wait_for(cleanup_complete.wait(), 1)

            except OSError as ex:
                if ex.errno == EADDRINUSE:
                    errors["base"] = "address_in_use"
                else:
                    errors["base"] = "connection_failed"
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({vol.Required("host"): str}),
                    errors=errors,
                )

            return self.async_create_entry(
                title=f"DayBetter Light {host}",
                data={"host": host},
            )

        # 显示表单让用户手动输入
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("host"): str}),
            errors=errors,
        )
