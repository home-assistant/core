"""Config flow for Indevolt integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN, SUPPORTED_MODELS
from .indevolt import Indevolt
from .utils import get_device_gen

_LOGGER = logging.getLogger(__name__)


class IndevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Indevolt."""

    VERSION = 1

    host = ""
    port: int
    model = ""
    device_sn = ""
    fw_version = ""

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step via user interface."""
        errors = {}
        if user_input is not None:
            self.host = user_input["host"]
            self.port = user_input.get("port", DEFAULT_PORT)
            self.model = user_input["model"]

            if get_device_gen(self.model) == 1:
                self.fw_version = "V1.3.0A_R006.072_M4848_00000039"
            else:
                self.fw_version = "V1.3.09_R00D.012_M4801_00000015"

            try:
                self.device_sn = await self.get_device_sn(self.host, self.port)

            except TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unknown error occurred while verifying device")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{self.model}_{self.device_sn}")
                self._abort_if_unique_id_configured()

                if not errors:
                    return self.async_create_entry(
                        title=f"{self.model} ({self.host})",
                        data={
                            "host": self.host,
                            "port": self.port,
                            "scan_interval": user_input.get(
                                "scan_interval", DEFAULT_SCAN_INTERVAL
                            ),
                            "sn": self.device_sn,
                            "fw_version": self.fw_version,
                            "model": self.model,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host"): str,
                    vol.Optional("port", default=DEFAULT_PORT): int,
                    vol.Optional("scan_interval", default=DEFAULT_SCAN_INTERVAL): int,
                    vol.Required("model"): vol.In(SUPPORTED_MODELS),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            self.host = user_input["host"]
            self.port = user_input["port"]
            self.model = user_input["model"]

            if get_device_gen(self.model) == 1:
                self.fw_version = "V1.3.0A_R006.072_M4848_00000039"
            else:
                self.fw_version = "V1.3.09_R00D.012_M4801_00000015"

            try:
                self.device_sn = await self.get_device_sn(self.host, self.port)

            except TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unknown error occurred while verifying device")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{self.model}_{self.device_sn}")
                self._abort_if_unique_id_mismatch(reason="another_device")

                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={
                        "host": self.host,
                        "port": self.port,
                        "scan_interval": user_input.get(
                            "scan_interval", DEFAULT_SCAN_INTERVAL
                        ),
                        "sn": self.device_sn,
                        "fw_version": self.fw_version,
                        "model": self.model,
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "host", default=reconfigure_entry.data.get("host")
                    ): str,
                    vol.Optional(
                        "port",
                        default=reconfigure_entry.data.get("port"),
                    ): int,
                    vol.Optional(
                        "scan_interval",
                        default=reconfigure_entry.data.get("scan_interval"),
                    ): int,
                    vol.Required(
                        "model",
                        default=reconfigure_entry.data.get("model"),
                    ): vol.In(SUPPORTED_MODELS),
                }
            ),
            description_placeholders={
                "title": reconfigure_entry.title,
            },
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self.host = discovery_info.host
        self.model = discovery_info.properties["product_type"]
        self.device_sn = discovery_info.properties["serial"]
        self.fw_version = discovery_info.properties["fw_version"]

        await self.async_set_unique_id(f"{self.model}_{self.device_sn}")
        self._abort_if_unique_id_configured(updates={"host": discovery_info.host})

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        assert self.host
        assert self.model
        assert self.device_sn

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.get_device_sn(self.host, DEFAULT_PORT)

            except TimeoutError:
                errors["base"] = "timeout"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unknown error occurred while verifying device")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{self.model} ({self.host})",
                    data={
                        "host": self.host,
                        "port": DEFAULT_PORT,
                        "scan_interval": DEFAULT_SCAN_INTERVAL,
                        "sn": self.device_sn,
                        "fw_version": self.fw_version,
                        "model": self.model,
                    },
                )

        self._set_confirm_only()

        name = f"{self.model} ({self.device_sn})"
        self.context["title_placeholders"] = {"name": name}

        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={
                "model": self.model,
                "sn": self.device_sn,
                "host": self.host,
            },
            errors=errors,
        )

    async def get_device_sn(self, host: str, port: int) -> str:
        """Get serial number from the device."""
        device = Indevolt(async_get_clientsession(self.hass), host, port)
        data = await device.fetch_data(0)
        return data.get("0", "unknown")
