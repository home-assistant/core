"""The config flow for the Prowl component."""

import logging
from typing import Any, override

import probatio
import prowlpy

from homeassistant.components.notify import SERVICE_NOTIFY
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY

from .const import CONF_LEGACY_SERVICE_NAME, CONF_NAMES, DOMAIN
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
        self._async_abort_entries_match({CONF_API_KEY: api_key})

        # Not validated: API key or connection problems surface on entry setup
        names: list[str | None] = import_data[CONF_NAMES]
        if names[0] and len(names) == 1:
            # The title is the name of the legacy notify service
            return self.async_create_entry(
                title=names[0],
                data={CONF_API_KEY: api_key},
            )
        # YAML without a name provides the notify.notify service
        service_names = [name or SERVICE_NOTIFY for name in names]
        return self.async_create_entry(
            title=", ".join(service_names) if len(names) > 1 else "Prowl",
            data={
                CONF_API_KEY: api_key,
                CONF_LEGACY_SERVICE_NAME: service_names[0],
            },
        )

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
