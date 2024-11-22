"""Config flow for Fully Kiosk Browser integration."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp.client_exceptions import ClientConnectorError
from fullykiosk import FullyKiosk
from fullykiosk.exceptions import FullyKioskError
import voluptuous as vol

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import DEFAULT_PORT, DOMAIN, LOGGER


class FullyKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fully Kiosk Browser."""

    VERSION = 1

    host: str

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device_info: dict[str, Any] = {}

    async def _create_entry(
        self,
        host: str,
        user_input: dict[str, Any],
        errors: dict[str, str],
        description_placeholders: dict[str, str] | Any = None,
    ) -> ConfigFlowResult | None:
        fully = FullyKiosk(
            async_get_clientsession(self.hass),
            host,
            DEFAULT_PORT,
            user_input[CONF_PASSWORD],
            use_ssl=user_input[CONF_SSL],
            verify_ssl=user_input[CONF_VERIFY_SSL],
        )

        try:
            async with asyncio.timeout(15):
                device_info = await fully.getDeviceInfo()
        except (
            ClientConnectorError,
            FullyKioskError,
            TimeoutError,
        ) as error:
            LOGGER.debug(error.args, exc_info=True)
            errors["base"] = "cannot_connect"
            description_placeholders["error_detail"] = str(error.args)
            return None
        except Exception as error:  # noqa: BLE001
            LOGGER.exception("Unexpected exception: %s", error)
            errors["base"] = "unknown"
            description_placeholders["error_detail"] = str(error.args)
            return None

        await self.async_set_unique_id(device_info["deviceID"], raise_on_progress=False)
        self._abort_if_unique_id_configured(updates=user_input)
        return self.async_create_entry(
            title=device_info["deviceName"],
            data={
                CONF_HOST: host,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_MAC: format_mac(device_info["Mac"]),
                CONF_SSL: user_input[CONF_SSL],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            result = await self._create_entry(
                user_input[CONF_HOST], user_input, errors, placeholders
            )
            if result:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_SSL, default=False): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            description_placeholders=placeholders,
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle dhcp discovery."""
        mac = format_mac(discovery_info.macaddress)

        for entry in self._async_current_entries():
            if entry.data[CONF_MAC] == mac:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=entry.data | {CONF_HOST: discovery_info.ip},
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(entry.entry_id)
                )
                return self.async_abort(reason="already_configured")

        return self.async_abort(reason="unknown")

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}
        if user_input is not None:
            result = await self._create_entry(self.host, user_input, errors)
            if result:
                return result

        placeholders = {
            "name": self._discovered_device_info["deviceName"],
            CONF_HOST: self.host,
        }
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_SSL, default=False): bool,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            description_placeholders=placeholders,
            errors=errors,
        )

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by MQTT discovery."""
        device_info: dict[str, Any] = json.loads(discovery_info.payload)
        device_id: str = device_info["deviceId"]
        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()

        self.host = device_info["hostname4"]
        self._discovered_device_info = device_info
        return await self.async_step_discovery_confirm()
