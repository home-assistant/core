"""Config flow for the Swisscom Internet-Box integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import SwisscomAuthError, SwisscomClient, SwisscomConnectionError
from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SwisscomConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swisscom Internet-Box."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> tuple[str | None, str]:
        """Validate credentials and return (unique_id, title)."""
        client = SwisscomClient(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        await client.login()
        info = await client.get_device_info()
        unique_id = format_mac(info["BaseMAC"]) if info.get("BaseMAC") else None
        title = info.get("ModelName") or "Internet-Box"
        return unique_id, title

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                unique_id, title = await self._validate(user_input)
            except SwisscomAuthError:
                errors["base"] = "invalid_auth"
            except SwisscomConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during Swisscom config flow")
                errors["base"] = "unknown"
            else:
                if unique_id:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a configuration from configuration.yaml."""
        try:
            unique_id, title = await self._validate(import_data)
        except SwisscomAuthError:
            return self.async_abort(reason="invalid_auth")
        except SwisscomConnectionError:
            return self.async_abort(reason="cannot_connect")

        if unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=import_data)
