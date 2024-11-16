"""Config Flow for OSO Energy."""

from collections.abc import Mapping
import logging
from typing import Any

from apyosoenergyapi import OSOEnergy
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_SCHEMA_STEP_USER = vol.Schema({vol.Required(CONF_API_KEY): str})


class OSOEnergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a OSO Energy config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Verify Subscription key
            if user_email := await self.get_user_email(user_input[CONF_API_KEY]):
                await self.async_set_unique_id(user_email)

                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), title=user_email, data=user_input
                    )

                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_email, data=user_input)

            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=_SCHEMA_STEP_USER,
            errors=errors,
        )

    async def get_user_email(self, subscription_key: str) -> str | None:
        """Return the user email for the provided subscription key."""
        try:
            websession = aiohttp_client.async_get_clientsession(self.hass)
            client = OSOEnergy(subscription_key, websession)
            return await client.get_user_email()
        except Exception:
            _LOGGER.exception("Unknown error occurred")
        return None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Re Authenticate a user."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _SCHEMA_STEP_USER, self._get_reauth_entry().data
            ),
        )
