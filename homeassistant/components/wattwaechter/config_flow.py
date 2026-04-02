"""Config flow for the WattWächter Plus integration."""

from __future__ import annotations

import logging
from typing import Any

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WattwaechterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WattWächter Plus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str = ""
        self._device_id: str = ""
        self._model: str = ""
        self._fw_version: str = ""
        self._mac: str = ""

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)

        self._host = str(discovery_info.host)

        properties = discovery_info.properties
        device_id_raw = properties.get("id", "")
        self._model = properties.get("model", "WW-Plus")
        self._fw_version = properties.get("ver", "")
        self._mac = properties.get("mac", "")

        self._device_id = device_id_raw.removeprefix("WWP-")

        if not self._device_id:
            return self.async_abort(reason="no_device_id")

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        session = async_get_clientsession(self.hass)
        client = Wattwaechter(self._host, session=session)
        try:
            await client.alive()
        except WattwaechterConnectionError:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": f"WattWächter {self._device_id}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm zeroconf discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input.get(CONF_TOKEN) or None

            if token:
                session = async_get_clientsession(self.hass)
                client = Wattwaechter(self._host, token=token, session=session)
                try:
                    await client.system_info()
                except WattwaechterAuthenticationError:
                    errors["base"] = "invalid_auth"
                except WattwaechterConnectionError:
                    errors["base"] = "cannot_connect"

            if not errors:
                device_name = await self._async_fetch_device_name(token)
                title = device_name or f"WattWächter {self._device_id}"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: self._host,
                        CONF_TOKEN: token,
                        CONF_DEVICE_ID: self._device_id,
                        CONF_DEVICE_NAME: device_name,
                        CONF_MODEL: self._model,
                        CONF_FW_VERSION: self._fw_version,
                        CONF_MAC: self._mac,
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TOKEN): str,
                }
            ),
            description_placeholders={
                "model": self._model or "WattWächter Plus",
                "firmware": self._fw_version or "unknown",
                "host": self._host or "",
                "device_id": self._device_id or "",
            },
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            token = user_input.get(CONF_TOKEN) or None

            session = async_get_clientsession(self.hass)
            client = Wattwaechter(host, token=token, session=session)

            try:
                alive = await client.alive()
            except WattwaechterConnectionError:
                errors["base"] = "cannot_connect"

            if not errors:
                fw_version = alive.version
                device_id: str = ""
                mac = ""
                model = "WW-Plus"

                try:
                    system_info = await client.system_info()
                except WattwaechterAuthenticationError:
                    errors["base"] = "invalid_auth"
                except WattwaechterConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    device_id = system_info.get_value("esp", "esp_id") or ""
                    fw_version = (
                        system_info.get_value("esp", "os_version") or fw_version
                    )
                    mac = system_info.get_value("wifi", "mac_address") or ""

            if not errors and not device_id:
                errors["base"] = "cannot_connect"

            if not errors:
                await self.async_set_unique_id(device_id)
                self._abort_if_unique_id_configured()

                device_name = ""
                try:
                    settings = await client.settings()
                except (
                    WattwaechterConnectionError,
                    WattwaechterAuthenticationError,
                ):
                    pass
                else:
                    device_name = settings.device_name

                title = device_name or f"WattWächter {device_id}"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: host,
                        CONF_TOKEN: token,
                        CONF_DEVICE_ID: device_id,
                        CONF_DEVICE_NAME: device_name,
                        CONF_MODEL: model,
                        CONF_FW_VERSION: fw_version,
                        CONF_MAC: mac,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def _async_fetch_device_name(self, token: str | None = None) -> str:
        """Try to fetch device_name from settings, return empty string on failure."""
        session = async_get_clientsession(self.hass)
        client = Wattwaechter(self._host, token=token, session=session)
        try:
            settings = await client.settings()
        except (WattwaechterConnectionError, WattwaechterAuthenticationError):
            return ""
        else:
            return settings.device_name
