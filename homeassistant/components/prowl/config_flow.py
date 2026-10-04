"""The config flow for the Prowl component."""

import logging
from typing import Any, override

import probatio
import prowlpy

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback

from .const import CONF_LEGACY_SERVICE_NAMES, DOMAIN
from .helpers import async_verify_key

_LOGGER = logging.getLogger(__name__)


class ProwlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Prowl component."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user configuration."""
        errors = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]
            self._async_abort_entries_match({CONF_API_KEY: api_key})

            errors = await self._validate_api_key(api_key)
            if not errors:
                return self.async_create_entry(
                    title="Prowl",
                    data={
                        CONF_API_KEY: api_key,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {probatio.Required(probatio.Secret(CONF_API_KEY)): str},
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a YAML notify platform configuration."""
        api_key = import_data[CONF_API_KEY]
        name = import_data.get(CONF_NAME)

        if result := self._async_add_legacy_service_name(api_key, name):
            return result

        if errors := await self._validate_api_key(api_key):
            return self.async_abort(reason=errors["base"])

        # Another import for this API key may have created the entry meanwhile
        if result := self._async_add_legacy_service_name(api_key, name):
            return result

        return self.async_create_entry(
            title=name or "Prowl",
            data={CONF_API_KEY: api_key, CONF_LEGACY_SERVICE_NAMES: [name]},
        )

    @callback
    def _async_add_legacy_service_name(
        self, api_key: str, name: str | None
    ) -> ConfigFlowResult | None:
        """Add a YAML legacy service name to the entry with the same API key."""
        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_API_KEY] != api_key:
                continue
            names: list[str | None] = entry.data.get(CONF_LEGACY_SERVICE_NAMES, [])
            if name in names:
                return self.async_abort(reason="already_configured")
            return self.async_update_and_abort(
                entry,
                data_updates={CONF_LEGACY_SERVICE_NAMES: [*names, name]},
                reason="already_configured",
            )
        return None

    async def _validate_api_key(self, api_key: str) -> dict[str, str]:
        """Validate the provided API key."""
        ret = {}
        try:
            if not await async_verify_key(self.hass, api_key):
                ret = {"base": "invalid_api_key"}
        except TimeoutError:
            ret = {"base": "api_timeout"}
        except prowlpy.APIError:
            ret = {"base": "bad_api_response"}
        return ret
