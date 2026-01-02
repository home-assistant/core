"""Config flow for the SystemNexa2 integration."""

from dataclasses import dataclass
import logging
import socket
from typing import Any

import aiohttp
from sn2.device import Device
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.network import is_ip_address

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


def _is_valid_host(ip_or_hostname: str) -> bool:
    if not ip_or_hostname:
        return False
    if is_ip_address(ip_or_hostname):
        return True
    try:
        socket.gethostbyname(ip_or_hostname)
    except socket.gaierror:
        return False
    return True


@dataclass
class _DiscoveryInfo:
    name: str
    host: str
    model: str
    device_id: str
    device_version: str


class SystemNexa2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the devices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: _DiscoveryInfo

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated flow."""

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_SCHEMA)

        return await self._async_add_by_ip_or_hostname(user_input[CONF_HOST])

    async def _async_add_by_ip_or_hostname(self, host_or_ip: str) -> ConfigFlowResult:
        if not _is_valid_host(host_or_ip):
            return self.async_abort(reason="invalid_host")
        temp_dev = await Device.initiate_device(
            host=host_or_ip,
            session=async_get_clientsession(self.hass),
        )

        try:
            info = await temp_dev.get_info()
        except (TimeoutError, aiohttp.ClientError):
            return self.async_abort(
                reason="no_connection", description_placeholders={CONF_HOST: host_or_ip}
            )
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(
                reason="unknown_connection_error",
                description_placeholders={CONF_HOST: host_or_ip},
            )

        device_id = info.information.unique_id
        device_model = info.information.model
        device_version = info.information.sw_version
        if device_id is None or device_model is None or device_version is None:
            return self.async_abort(
                reason="unsupported_model",
                description_placeholders={
                    ATTR_MODEL: str(device_model),
                    ATTR_SW_VERSION: str(device_version),
                },
            )

        self._discovered_device = _DiscoveryInfo(
            name=info.information.name or "Unknown Name",
            host=host_or_ip,
            device_id=device_id,
            model=device_model,
            device_version=device_version,
        )
        await self._async_validate_discovered_device()

        return await self._async_create_device_entry()

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        device_id = discovery_info.properties.get("id")
        device_model = discovery_info.properties.get("model")
        device_version = discovery_info.properties.get("version")
        if device_id is None or device_model is None or device_version is None:
            return self.async_abort(
                reason="unsupported_model",
                description_placeholders={
                    ATTR_MODEL: str(device_model),
                    ATTR_SW_VERSION: str(device_version),
                },
            )
        self._discovered_device = _DiscoveryInfo(
            name=discovery_info.name.split(".")[0],
            host=discovery_info.host,
            device_id=device_id,
            model=device_model,
            device_version=device_version,
        )
        await self._async_validate_discovered_device()

        return await self.async_step_discovery_confirm()

    async def _async_validate_discovered_device(self) -> None:
        supported, error = Device.is_device_supported(
            model=self._discovered_device.model,
            device_version=self._discovered_device.device_version,
        )
        if not supported:
            _LOGGER.error("Unsupported model: %s", error)
            raise AbortFlow(
                reason="unsupported_model",
                description_placeholders={
                    ATTR_MODEL: str(self._discovered_device.model),
                    ATTR_SW_VERSION: str(self._discovered_device.device_version),
                },
            )

        await self.async_set_unique_id(self._discovered_device.device_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self._discovered_device.host}
        )

        _LOGGER.info(
            "Configuring device %s: %s at %s",
            self._discovered_device.name,
            self._discovered_device.model,
            self._discovered_device.host,
        )
        self.context["title_placeholders"] = {
            "name": self._discovered_device.name,
            "model": self._discovered_device.model or "Unknown model",
        }

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        if user_input is not None and self._discovered_device is not None:
            return await self._async_create_device_entry()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": self._discovered_device.name},
        )

    async def _async_create_device_entry(self) -> ConfigFlowResult:
        device_name = self._discovered_device.name
        device_model = self._discovered_device.model
        return self.async_create_entry(
            title=f"{device_name} ({device_model})",
            data={
                CONF_HOST: self._discovered_device.host,
                CONF_NAME: self._discovered_device.name,
                CONF_MODEL: self._discovered_device.model,
                CONF_DEVICE_ID: self._discovered_device.device_id,
            },
        )
