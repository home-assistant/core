"""Config flow for SRP Energy."""
from __future__ import annotations

from typing import Any

from srpenergy.client import SrpEnergyClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_IS_TOU, DEFAULT_NAME, DOMAIN, LOGGER


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    srp_client = SrpEnergyClient(
        data[CONF_ID],
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
    )

    is_valid = await hass.async_add_executor_job(srp_client.validate)

    LOGGER.debug("Is user input valid: %s", is_valid)
    if not is_valid:
        raise InvalidAuth

    return is_valid


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an SRP Energy config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        default_title: str = DEFAULT_NAME

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if self.hass.config.location_name:
            default_title = self.hass.config.location_name

        if user_input:
            try:
                await validate_input(self.hass, user_input)
            except ValueError:
                # Thrown when the account id is malformed
                errors["base"] = "invalid_account"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                return self.async_create_entry(title=default_title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ID): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_IS_TOU, default=False): bool,
                }
            ),
            errors=errors or {},
        )


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
