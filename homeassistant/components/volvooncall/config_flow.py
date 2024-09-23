"""Config flow for Volvo On Call integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol
from volvooncall import Connection

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_REGION,
    CONF_UNIT_SYSTEM,
    CONF_USERNAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MUTABLE,
    DOMAIN,
    UNIT_SYSTEM_IMPERIAL,
    UNIT_SYSTEM_METRIC,
    UNIT_SYSTEM_SCANDINAVIAN_MILES,
)
from .errors import InvalidAuth
from .models import VolvoData

_LOGGER = logging.getLogger(__name__)


class VolvoOnCallConfigFlow(ConfigFlow, domain=DOMAIN):
    """VolvoOnCall config flow."""

    VERSION = 1
    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user step."""
        errors = {}
        defaults = {
            CONF_USERNAME: "",
            CONF_PASSWORD: "",
            CONF_REGION: None,
            CONF_MUTABLE: True,
            CONF_UNIT_SYSTEM: UNIT_SYSTEM_METRIC,
        }

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME])

            if not self._reauth_entry:
                self._abort_if_unique_id_configured()

            try:
                await self.is_valid(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unhandled exception in user step")
                errors["base"] = "unknown"
            if not errors:
                if self._reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry, data=self._reauth_entry.data | user_input
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        elif self._reauth_entry:
            for key in defaults:
                defaults[key] = self._reauth_entry.data.get(key)

        user_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=defaults[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD, default=defaults[CONF_PASSWORD]): str,
                vol.Required(CONF_REGION, default=defaults[CONF_REGION]): vol.In(
                    {"na": "North America", "cn": "China", None: "Rest of world"}
                ),
                vol.Optional(
                    CONF_UNIT_SYSTEM, default=defaults[CONF_UNIT_SYSTEM]
                ): vol.In(
                    {
                        UNIT_SYSTEM_METRIC: "Metric",
                        UNIT_SYSTEM_SCANDINAVIAN_MILES: (
                            "Metric with Scandinavian Miles"
                        ),
                        UNIT_SYSTEM_IMPERIAL: "Imperial",
                    }
                ),
                vol.Optional(CONF_MUTABLE, default=defaults[CONF_MUTABLE]): bool,
            },
        )

        return self.async_show_form(
            step_id="user", data_schema=user_schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def is_valid(self, user_input):
        """Check for user input errors."""

        session = async_get_clientsession(self.hass)

        region: str | None = user_input.get(CONF_REGION)

        connection = Connection(
            session=session,
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            service_url=None,
            region=region,
        )

        test_volvo_data = VolvoData(self.hass, connection, user_input)

        await test_volvo_data.auth_is_valid()
