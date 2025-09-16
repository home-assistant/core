"""Config flow for solarman integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN

# from solarman_opendata import get_config
from .solarman import get_config

_LOGGER = logging.getLogger(__name__)


class SolarmanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solarman."""

    VERSION = 1

    host = ""
    model = ""
    device_sn = ""
    fw_version = ""

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step via user interface."""
        errors = {}
        if user_input is not None:
            self.host = user_input["host"]
            port = user_input.get("port", DEFAULT_PORT)

            try:
                config_data = await get_config(
                    async_get_clientsession(self.hass), self.host
                )

                device_info = config_data.get("device", config_data)

                self.device_sn = device_info.get("sn", "unknown")
                self.fw_version = device_info.get("fw", "unknown")
                self.model = device_info.get("type", "unknown")

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
                            "port": port,
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
            port = user_input.get("port", DEFAULT_PORT)

            try:
                config_data = await get_config(
                    async_get_clientsession(self.hass), self.host
                )

                device_info = config_data.get("device", config_data)

                self.device_sn = device_info.get("sn", "unknown")
                self.fw_version = device_info.get("fw", "unknown")
                self.model = device_info.get("type", "unknown")

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
                        "port": port,
                        "scan_interval": user_input.get(
                            "scan_interval", DEFAULT_SCAN_INTERVAL
                        ),
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
        if (
            "product_type" not in discovery_info.properties
            or "serial" not in discovery_info.properties
            or "fw_version" not in discovery_info.properties
        ):
            return self.async_abort(reason="invalid_discovery_parameters")

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
                await get_config(
                    async_get_clientsession(self.hass), self.host
                )

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
