"""Config flow for the Solyx Energy integration."""

from typing import Any, override

from solyx_energy_api.client import SolyxEnergyApiClient
from solyx_energy_api.exceptions import (
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    BASE_URL,
    CONF_NYMO_CLIENT_ID,
    CONF_NYMO_CLIENT_SECRET,
    CONF_NYMO_DEVICE_ID,
    DOMAIN,
    REALM_ID,
)

# Schema definition for the initial user setup
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NYMO_CLIENT_ID): TextSelector(),
        vol.Required(CONF_NYMO_CLIENT_SECRET): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD),
        ),
        vol.Required(CONF_NYMO_DEVICE_ID): TextSelector(),
    },
)


class SolyxEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the main config flow for the Solyx Energy integration."""

    VERSION = 1

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step when setting up the integration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_NYMO_DEVICE_ID])
            self._abort_if_unique_id_configured()

            try:
                await self._validate_input(user_input)
            except SolyxEnergyAuthError:
                errors["base"] = "invalid_auth"
            except (SolyxEnergyTokenError, SolyxEnergyDataError) as _err:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Nymo {user_input[CONF_NYMO_DEVICE_ID]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> None:
        """Validate user input by testing the connection to the Solyx Cloud."""
        session = async_get_clientsession(self.hass)
        client = SolyxEnergyApiClient(
            session=session,
            nymo_client_id=user_input[CONF_NYMO_CLIENT_ID],
            nymo_client_secret=user_input[CONF_NYMO_CLIENT_SECRET],
            base_url=BASE_URL,
            realm_id=REALM_ID,
        )
        await client.async_test_connection(user_input[CONF_NYMO_DEVICE_ID])
