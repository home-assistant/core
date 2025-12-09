"""Config flow for Vitrea integration."""

from __future__ import annotations

import logging
from typing import Any

from vitreaclient import VitreaClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class VitreaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vitrea."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Set unique_id to prevent duplicates based on host
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            try:
                # Test connection
                client = VitreaClient(host, port)
                await client.connect()
                await client.disconnect()
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except TimeoutError:
                errors["base"] = "timeout_connect"
            except Exception:  # Allowed in config flow
                _LOGGER.exception("Unexpected exception during Vitrea setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Vitrea ({host})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                # Test connection
                client = VitreaClient(host, port)
                await client.connect()
                await client.disconnect()
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except TimeoutError:
                errors["base"] = "timeout_connect"
            except Exception:  # Allowed in config flow
                _LOGGER.exception("Unexpected exception during Vitrea reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Optional(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=errors,
        )
