"""Config flow for SRP Energy."""

from __future__ import annotations

from typing import Any

from srpenergy.client import SrpEnergyClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ID, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_IS_TOU, DOMAIN, LOGGER


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


class SRPEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an SRP Energy config flow."""

    VERSION = 1

    @callback
    def _show_form(self, errors: dict[str, Any]) -> ConfigFlowResult:
        """Show the form to the user."""
        LOGGER.debug("Show Form")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                    vol.Required(CONF_ID): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_IS_TOU, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        LOGGER.debug("Config entry")
        errors: dict[str, str] = {}
        if not user_input:
            return self._show_form(errors)

        try:
            await validate_input(self.hass, user_input)
        except ValueError:
            # Thrown when the account id is malformed
            errors["base"] = "invalid_account"
            return self._show_form(errors)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            return self._show_form(errors)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(user_input[CONF_ID])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
