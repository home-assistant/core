"""Config flow for the Hydrawise integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aiohttp import ClientError
from pydrawise import legacy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY

from .const import DOMAIN, LOGGER


class HydrawiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydrawise."""

    VERSION = 1

    async def _create_entry(
        self, api_key: str, *, on_failure: Callable[[str], ConfigFlowResult]
    ) -> ConfigFlowResult:
        """Create the config entry."""
        api = legacy.LegacyHydrawiseAsync(api_key)
        try:
            # Skip fetching zones to save on metered API calls.
            user = await api.get_user(fetch_zones=False)
        except TimeoutError:
            return on_failure("timeout_connect")
        except ClientError as ex:
            LOGGER.error("Unable to connect to Hydrawise cloud service: %s", ex)
            return on_failure("cannot_connect")

        await self.async_set_unique_id(f"hydrawise-{user.customer_id}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title="Hydrawise", data={CONF_API_KEY: api_key})

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup."""
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            return await self._create_entry(api_key, on_failure=self._show_form)
        return self._show_form()

    def _show_form(self, error_type: str | None = None) -> ConfigFlowResult:
        errors = {}
        if error_type is not None:
            errors["base"] = error_type
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
