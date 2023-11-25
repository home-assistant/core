"""Will write later."""

import logging

from decora_wifi import DecoraWiFiSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("email"): str,
        vol.Required("password"): str,
    }
)


class DecoreWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Will write later."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Will write later."""

        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input["email"]
            password = user_input["password"]

            try:
                unique_id, session = await async_validate_input(
                    self.hass, email, password
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # No Errors
                existing_entry = await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    # Reload the config entry otherwise devices will remain unavailable
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(existing_entry.entry_id)
                    )

                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        # CONF_DEVICES: [],
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


async def async_validate_input(
    hass: HomeAssistant, email: str, password: str
) -> tuple[str, DecoraWiFiSession]:
    """Will add later."""
    session = DecoraWiFiSession()
    user = await hass.async_add_executor_job(lambda: session.login(email, password))
    if not user:
        raise InvalidAuth("invalid authentication")
    return email, session


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
