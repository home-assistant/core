"""Config flow for the Vallox integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from vallox_websocket_api import Vallox, ValloxApiException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.network import is_ip_address

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


async def validate_host(hass: HomeAssistant, host: str) -> None:
    """Validate that the user input allows us to connect."""

    if not is_ip_address(host):
        raise InvalidHost(f"Invalid IP address: {host}")

    client = Vallox(host)
    await client.fetch_metric_data()


class ValloxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Vallox integration."""

    VERSION = 1

    _context_entry: ConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=CONFIG_SCHEMA,
            )

        errors: dict[str, str] = {}

        host = user_input[CONF_HOST]

        self._async_abort_entries_match({CONF_HOST: host})

        try:
            await validate_host(self.hass, host)
        except InvalidHost:
            errors[CONF_HOST] = "invalid_host"
        except ValloxApiException:
            errors[CONF_HOST] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors[CONF_HOST] = "unknown"
        else:
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    **user_input,
                    CONF_NAME: DEFAULT_NAME,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, {CONF_HOST: host}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the Vallox device host address."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry
        self._context_entry = entry
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the Vallox device host address."""
        if not user_input:
            return self.async_show_form(
                step_id="reconfigure_confirm",
                data_schema=self.add_suggested_values_to_schema(
                    CONFIG_SCHEMA, {CONF_HOST: self._context_entry.data.get(CONF_HOST)}
                ),
            )

        updated_host = user_input[CONF_HOST]

        if self._context_entry.data.get(CONF_HOST) != updated_host:
            self._async_abort_entries_match({CONF_HOST: updated_host})

        errors: dict[str, str] = {}

        try:
            await validate_host(self.hass, updated_host)
        except InvalidHost:
            errors[CONF_HOST] = "invalid_host"
        except ValloxApiException:
            errors[CONF_HOST] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors[CONF_HOST] = "unknown"
        else:
            return self.async_update_reload_and_abort(
                self._context_entry,
                data={**self._context_entry.data, CONF_HOST: updated_host},
                reason="reconfigure_successful",
            )

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, {CONF_HOST: updated_host}
            ),
            errors=errors,
        )


class InvalidHost(HomeAssistantError):
    """Error to indicate an invalid host was input."""
