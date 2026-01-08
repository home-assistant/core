"""Config flow for Indevolt integration."""

import logging
from typing import Any

from aiohttp import ClientError
from indevolt_api import IndevoltAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DEFAULT_PORT = 8080


class IndevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for Indevolt integration."""

    VERSION = 2
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._discovered_host: str | None = None
        self._discovered_port: int | None = None
        self._discovered_device_model: str | None = None
        self._reconfig_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, device_data = await self._async_validate_input(user_input)

            if not errors and device_data:
                await self.async_set_unique_id(
                    f"{device_data['device_model']}_{device_data['sn']}"
                )

                # Handle reconfigure flow
                if self._reconfig_entry is not None:
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
                    return self.async_update_reload_and_abort(
                        self._reconfig_entry,
                        data={
                            "host": user_input["host"],
                            "port": user_input["port"],
                            **device_data,
                        },
                    )

                # Handle initial setup
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"INDEVOLT {device_data['device_model']} ({user_input['host']})",
                    data={
                        "host": user_input["host"],
                        "port": user_input["port"],
                        **device_data,
                    },
                )

        # Get defaults for reconfigure
        defaults: dict[str, Any] = {}
        if self._reconfig_entry is not None:
            defaults = {
                "host": self._reconfig_entry.data.get("host"),
                "port": self._reconfig_entry.data.get("port", DEFAULT_PORT),
            }

        return self.async_show_form(
            step_id="reconfigure" if self._reconfig_entry else "user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=defaults.get("host")): str,
                    vol.Optional(
                        "port", default=defaults.get("port", DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initiated by the user."""
        self._reconfig_entry = self._get_reconfigure_entry()
        return await self.async_step_user(user_input)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT

        try:
            device_data = await self._async_get_device_data(host, port)

            if not device_data["sn"] or device_data["sn"] == "unknown":
                return self.async_abort(reason="cannot_connect")

            await self.async_set_unique_id(
                f"{device_data['device_model']}_{device_data['sn']}"
            )
            self._abort_if_unique_id_configured(updates={"host": host, "port": port})

            self.context["title_placeholders"] = {"name": device_data["device_model"]}
            self._discovered_host = host
            self._discovered_port = port
            self._discovered_device_model = device_data["device_model"]

            return await self.async_step_zeroconf_confirm()

        except (TimeoutError, ConnectionError, ClientError):
            _LOGGER.debug("Failed to connect to discovered device at %s:%s", host, port)
            return self.async_abort(reason="cannot_connect")

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm zeroconf discovery by user."""
        if user_input is not None:
            assert self._discovered_host is not None
            assert self._discovered_port is not None

            try:
                device_data = await self._async_get_device_data(
                    self._discovered_host,
                    self._discovered_port,
                )

                return self.async_create_entry(
                    title=f"INDEVOLT {device_data['device_model']} ({self._discovered_host})",
                    data={
                        "host": self._discovered_host,
                        "port": self._discovered_port,
                        **device_data,
                    },
                )
            except (TimeoutError, ConnectionError, ClientError):
                return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "host": self._discovered_host or "",
                "type": self._discovered_device_model or "unknown",
            },
        )

    async def _async_validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any] | None]:
        """Validate user input and return errors dict and device data."""
        errors = {}
        device_data = None

        try:
            device_data = await self._async_get_device_data(
                user_input["host"], user_input["port"]
            )
        except TimeoutError:
            errors["base"] = "timeout"
        except (ConnectionError, ClientError):
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unknown error occurred while verifying device")
            errors["base"] = "unknown"

        return errors, device_data

    async def _async_get_device_data(self, host: str, port: int) -> dict[str, Any]:
        """Get device data (type, serial number, firmware version, ...) from API."""
        api = IndevoltAPI(host, port, async_get_clientsession(self.hass))
        config_data = await api.get_config()
        device_data = config_data.get("device", {})

        return {
            "sn": device_data.get("sn", "unknown"),
            "fw_version": device_data.get("fw", "unknown"),
            "device_model": device_data.get("type", "unknown"),
            "generation": device_data.get("generation", 1),
        }
