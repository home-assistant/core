"""Config flow for the Hetzner Cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

from hcloud import APIException, Client
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class HetznerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hetzner Cloud."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_API_TOKEN]
            unique_id = hashlib.sha256(token.encode()).hexdigest()[:12]

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                client = Client(token=token)
                await self.hass.async_add_executor_job(client.load_balancers.get_all)
            except APIException:
                LOGGER.exception("Error connecting to API")
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error connecting to API")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="Hetzner Cloud",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_API_TOKEN]

            try:
                client = Client(token=token)
                await self.hass.async_add_executor_job(client.load_balancers.get_all)
            except APIException:
                LOGGER.exception("Error connecting to API during reauth")
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error connecting during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )
