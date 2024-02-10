"""Config flow for Fujitsu HVAC (based on Ayla IOT) integration."""
from asyncio import timeout
import logging
from typing import Any

from ayla_iot_unofficial import AylaAuthError, new_ayla_api
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import API_TIMEOUT, CONF_EUROPE, DOMAIN, FGLAIR_APP_ID, FGLAIR_APP_SECRET

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_EUROPE): bool,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu HVAC (based on Ayla IOT)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_USERNAME].lower()}")
            self._abort_if_unique_id_configured()

            api = new_ayla_api(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                FGLAIR_APP_ID,
                FGLAIR_APP_SECRET,
                europe=user_input[CONF_EUROPE],
            )
            try:
                async with timeout(API_TIMEOUT):
                    await api.async_sign_in()
            except TimeoutError:
                errors["base"] = "cannot_connect"
            except AylaAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if len(errors) == 0:
                return self.async_create_entry(
                    title=f"Fujitsu HVAC ({user_input[CONF_USERNAME]})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
