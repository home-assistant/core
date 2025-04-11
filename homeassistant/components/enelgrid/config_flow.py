import logging
from typing import Any, Mapping

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import (
    CONF_PASSWORD,
    CONF_POD,
    CONF_PRICE_PER_KWH,
    CONF_USER_NUMBER,
    CONF_USERNAME,
    DOMAIN,
)
from .login import EnelGridSession

_LOGGER = logging.getLogger(__name__)


class EnelGridConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for enelgrid."""

    VERSION = 1

    def __init__(self):
        self.reauth_entry = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step where the user configures the integration."""
        errors = {}
        if getattr(self, "reauth_entry", None):
            defaults = self.reauth_entry.data
        else:
            defaults = {}

        if user_input is not None:
            try:
                session = EnelGridSession(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_POD],
                    user_input[CONF_USER_NUMBER],
                )
                await session.login()  # 🔐 Credential check here
                await session.close()
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
                # raise ConfigEntryAuthFailed("Invalid credentials")
            except TimeoutError:
                raise ConfigEntryNotReady("Server timed out")
            except Exception as err:
                _LOGGER.exception(f"Failed to login: {err}")
                errors["base"] = "unknown"

            else:
                pod = user_input[CONF_POD]
                await self.async_set_unique_id(pod)

                if not self.reauth_entry:
                    self._abort_if_unique_id_configured()

                if self.reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=user_input
                    )
                    return self.async_abort(reason="reauth_successful")

                # Save all user-provided data to the config entry
                return self.async_create_entry(
                    title=f"Enel Account ({user_input[CONF_POD]})", data=user_input
                )

        # Show the form if user_input is None
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_POD, default=defaults.get(CONF_POD, "")): str,
                    vol.Required(
                        CONF_USER_NUMBER, default=defaults.get(CONF_USER_NUMBER, 0)
                    ): int,
                    vol.Required(
                        CONF_PRICE_PER_KWH,
                        default=defaults.get(CONF_PRICE_PER_KWH, 0.33),
                    ): vol.Coerce(float),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Perform reauth upon an API authentication error."""
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="missing_entry_id")

        self.reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        if self.reauth_entry is None:
            return self.async_abort(reason="entry_not_found")

        return await self.async_step_user()


@callback
def async_get_options_flow(config_entry):
    """Return the options flow handler if you want to add optional future settings."""
    return EnelGridOptionsFlowHandler(config_entry)


class EnelGridOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle any future options flow (optional)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
