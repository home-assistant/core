"""Config flow for Fujitsu HVAC (based on Ayla IOT) integration."""

from collections.abc import Mapping
import logging
from typing import Any

from ayla_iot_unofficial import AylaAuthError, new_ayla_api
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import API_TIMEOUT, CONF_EUROPE, DOMAIN, FGLAIR_APP_ID, FGLAIR_APP_SECRET

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_EUROPE): bool,
    }
)


class FujitsuHVACConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu HVAC (based on Ayla IOT)."""

    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input:
            if not self.reauth_entry:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
            elif user_input[CONF_USERNAME] != self.reauth_entry.data[CONF_USERNAME]:
                return self.async_abort(reason="wrong_account")

            api = new_ayla_api(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                FGLAIR_APP_ID,
                FGLAIR_APP_SECRET,
                europe=user_input[CONF_EUROPE],
                timeout=API_TIMEOUT,
            )
            try:
                await api.async_sign_in()
            except TimeoutError:
                errors["base"] = "cannot_connect"
            except AylaAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self.reauth_entry:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data=user_input
                    )
                    await self.hass.config_entries.async_reload(
                        self.reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=f"Fujitsu HVAC ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
