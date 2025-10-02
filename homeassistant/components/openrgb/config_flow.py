"""Config flow for the OpenRGB integration."""

from __future__ import annotations

import logging
from typing import Any

from openrgb import OpenRGBClient
from openrgb.utils import OpenRGBDisconnected, SDKVersionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DEFAULT_CLIENT_NAME, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, host: str, port: int) -> None:
    """Validate the user input allows us to connect."""

    def _try_connect(host: str, port: int) -> None:
        """Validate connection to OpenRGB server (sync function for executor)."""
        client = OpenRGBClient(host, port, DEFAULT_CLIENT_NAME)
        client.disconnect()

    await hass.async_add_executor_job(_try_connect, host, port)


class OpenRGBConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenRGB."""

    VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the OpenRGB SDK Server."""
        reconfigure_entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            server_slug = f"{host}:{port}"

            try:
                await validate_input(self.hass, host, port)
            except (
                ConnectionRefusedError,
                OpenRGBDisconnected,
                OSError,
                SDKVersionError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK Server at %s",
                    server_slug,
                )
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={CONF_HOST: host, CONF_PORT: port},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=reconfigure_entry.data[CONF_HOST],
                    ): str,
                    vol.Required(
                        CONF_PORT,
                        default=reconfigure_entry.data[CONF_PORT],
                    ): cv.port,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            server_slug = f"{host}:{port}"

            try:
                await validate_input(self.hass, host, port)
            except (
                ConnectionRefusedError,
                OpenRGBDisconnected,
                OSError,
                SDKVersionError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception(
                    "Unknown error while connecting to OpenRGB SDK Server at %s",
                    server_slug,
                )
                errors["base"] = "unknown"
            else:
                # Use host:port as unique ID
                unique_id = f"{host}:{port}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = f"OpenRGB ({host}:{port})"

                return self.async_create_entry(
                    title=title, data={CONF_HOST: host, CONF_PORT: port}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                }
            ),
            errors=errors,
        )
