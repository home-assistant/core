"""Config flow for the Open Hardware Monitor integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv

DOMAIN = "openhardwaremonitor"
CONF_POLLING_ENABLED = "polling_enabled"


class OpenHardwareMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Open Hardware Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, 8085)
            polling_enabled = user_input.get(CONF_POLLING_ENABLED, True)

            # Prevent duplicate entries by unique_id (host:port)
            unique_id = f"{host}:{port}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Validate connection
            try:
                await self._async_test_connection(host, port)
            except TimeoutError:
                errors["base"] = (
                    "Connection timed out. Make sure the Open Hardware Monitor server is running and accessible, and that the host and port are correct."
                )
            except requests.exceptions.ConnectionError:
                errors["base"] = (
                    "Connection to the Open Hardware Monitor server failed."
                )

            except Exception:  # pylint: disable=broad-except  # noqa: BLE001
                errors["base"] = (
                    "An unknown error occurred. Please check the logs for more details."
                )
            else:
                return self.async_create_entry(
                    title=f"Open Hardware Monitor ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_POLLING_ENABLED: polling_enabled,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_data_schema(),
            errors=errors,
        )

    def _get_data_schema(self) -> vol.Schema:
        """Return the schema for user input."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=8085): cv.port,
                vol.Optional(CONF_POLLING_ENABLED, default=True): cv.boolean,
            }
        )

    async def _async_test_connection(self, host: str, port: int) -> None:
        """Test connection to Open Hardware Monitor server."""
        url = f"http://{host}:{port}/data.json"
        timeout = aiohttp.ClientTimeout(total=5)
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(url) as response,
        ):
            response.raise_for_status()
