"""Config flow for the Ridder HortiMaX Pro (HortOS) integration."""

from typing import Any, override

from aiohortos import HortosAuthenticationError, HortosClient, HortosError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, LOGGER

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="api_key")
        ),
    }
)


class HortimaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ridder HortiMaX Pro."""

    async def _async_validate(self, api_key: str, errors: dict[str, str]) -> str | None:
        """Authenticate and list controllers, returning the organisation id."""
        client = HortosClient(api_key, session=async_get_clientsession(self.hass))
        try:
            tokens = await client.authenticate()
            devices = await client.get_device_names()
        except HortosAuthenticationError:
            errors["base"] = "invalid_auth"
        except HortosError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating the HortOS API")
            errors["base"] = "unknown"
        else:
            if not devices:
                errors["base"] = "no_devices"
            elif tokens.organisation is None or tokens.organisation.id is None:
                # Every API key is issued under an organisation, so this only
                # happens if the API changes shape.
                LOGGER.error("HortOS reported no organisation for this API key")
                errors["base"] = "unknown"
            else:
                return tokens.organisation.id
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            organisation_id = await self._async_validate(
                user_input[CONF_API_KEY], errors
            )
            if not errors:
                await self.async_set_unique_id(organisation_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Ridder HortiMaX Pro", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )
