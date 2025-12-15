"""Config flow for the SystemNexa2 integration."""

from dataclasses import dataclass
import logging
from typing import Any

from sn2.device import Device
import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, CONF_NAME
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class _DiscoveryInfo:
    name: str
    host: str
    model: str
    device_id: str
    device_version: str


class SN2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the devices."""

    VERSION = 1

    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: _DiscoveryInfo
        self.data_schema = {
            vol.Required(CONF_HOST): str,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user-initiated flow."""

        if user_input is None:
            return self.async_show_form(data_schema=vol.Schema(self.data_schema))

        return await self._async_step_add_by_ip_or_hostname(user_input[CONF_HOST])

    async def _async_step_add_by_ip_or_hostname(
        self, host_or_ip: str
    ) -> ConfigFlowResult:
        temp_dev = Device(host=host_or_ip)
        try:
            info = await temp_dev.get_info()
            device_id = info.information.unique_id
            device_model = info.information.model
            device_version = info.information.sw_version
            if device_id is None or device_model is None or device_version is None:
                return self.async_abort(
                    reason="unsupported_model",
                    description_placeholders={
                        "model": str(device_id),
                        "version": str(device_model),
                    },
                )

            self._discovered_device = _DiscoveryInfo(
                name=info.information.name or "Unknown Name",
                host=host_or_ip,
                device_id=device_id,
                model=device_model,
                device_version=device_version,
            )
        except Exception:  # noqa: BLE001
            return self.async_abort(
                reason="no_connection", description_placeholders={"host": host_or_ip}
            )

        res = await self._async_step_try_add()
        if res is not None:
            return res
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
                    "model": str(device_id),
                    "version": str(device_model),
                },
            )
        self._discovered_device = _DiscoveryInfo(
            name=discovery_info.name.split(".")[0],
            host=discovery_info.host,
            device_id=device_id,
            model=device_model,
            device_version=device_version,
        )
        res = await self._async_step_try_add()
        if res is not None:
            return res
        return await self.async_step_discovery_confirm()

    async def _async_step_try_add(self) -> ConfigFlowResult | None:
        if not Device.is_device_supported(
            model=self._discovered_device.model,
            device_version=self._discovered_device.device_version,
        ):
            return self.async_abort(
                reason="unsupported_model",
                description_placeholders={
                    "model": str(self._discovered_device.model),
                    "version": str(self._discovered_device.device_version),
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
        return None

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
