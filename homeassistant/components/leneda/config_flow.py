"""Config flow for Leneda integration."""

from __future__ import annotations

from typing import Any, Final

from leneda import LenedaClient
from leneda.exceptions import ForbiddenException, UnauthorizedException
from leneda.obis_codes import ObisCode
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_API_TOKEN, CONF_ENERGY_ID, DOMAIN

# Setup types
SETUP_TYPE_PROBE: Final = "probe"
SETUP_TYPE_MANUAL: Final = "manual"

# Error messages
ERROR_INVALID_METERING_POINT: Final = "invalid_metering_point"
ERROR_SELECT_AT_LEAST_ONE: Final = "select_at_least_one"
ERROR_DUPLICATE_METERING_POINT: Final = "duplicate_metering_point"
ERROR_FORBIDDEN: Final = "forbidden"
ERROR_UNAUTHORIZED: Final = "unauthorized"


class LenedaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Leneda (main entry: authentication only)."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_token: str = ""
        self._energy_id: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ENERGY_ID])
            self._abort_if_unique_id_configured()
            self._api_token = user_input[CONF_API_TOKEN]
            self._energy_id = user_input[CONF_ENERGY_ID]

            # Validate authentication by making a test API call
            client = LenedaClient(
                api_key=self._api_token,
                energy_id=self._energy_id,
            )
            try:
                # Use a dummy metering point ID to test authentication
                await client.probe_metering_point_obis_code(
                    "dummy-metering-point", ObisCode.ELEC_CONSUMPTION_ACTIVE
                )
            except UnauthorizedException:
                errors = {"base": ERROR_UNAUTHORIZED}
            except ForbiddenException:
                errors = {"base": ERROR_FORBIDDEN}
            else:
                return self.async_create_entry(
                    title=self._energy_id,
                    data={
                        CONF_API_TOKEN: self._api_token,
                        CONF_ENERGY_ID: self._energy_id,
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                            autocomplete="leneda-api-token",
                        )
                    ),
                    vol.Required(CONF_ENERGY_ID): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                            autocomplete="leneda-energy-id",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_config_entry_title(config_entry: ConfigEntry) -> str:
        """Get the title for the config entry."""
        return config_entry.data.get(CONF_ENERGY_ID, "Leneda")
