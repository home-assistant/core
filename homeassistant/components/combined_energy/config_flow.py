"""Config flow for Combined Energy integration."""
from __future__ import annotations

from typing import Any

from combined_energy import CombinedEnergy
from combined_energy.exceptions import (
    CombinedEnergyAuthError,
    CombinedEnergyError,
    CombinedEnergyPermissionError,
    CombinedEnergyTimeoutError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_INSTALLATION_ID, DEFAULT_NAME, DOMAIN, LOGGER


class CombinedEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Combined Energy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    async def _check_installation(
        self, username: str, password: str, installation_id: int
    ) -> bool:
        """Check if we can connect to the combined energy service."""
        api = CombinedEnergy(
            username,
            password,
            installation_id,
            session=async_get_clientsession(self.hass),
        )
        try:
            await api.installation()
        except CombinedEnergyAuthError:
            self._errors["base"] = "invalid_auth"
        except CombinedEnergyPermissionError:
            self._errors[CONF_INSTALLATION_ID] = "installation_not_accessible"
        except CombinedEnergyTimeoutError:
            self._errors["base"] = "cannot_connect"
        except CombinedEnergyError:
            LOGGER.exception("Unexpected error verifying connection to API")
            self._errors["base"] = "unknown"
        else:
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._errors = {}

        if user_input:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            installation_id = user_input[CONF_INSTALLATION_ID]

            await self.async_set_unique_id(str(installation_id))
            self._abort_if_unique_id_configured()

            can_connect = await self._check_installation(
                username, password, installation_id
            )
            if can_connect:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_INSTALLATION_ID: installation_id,
                    },
                )

        else:
            user_input = {
                CONF_NAME: DEFAULT_NAME,
                CONF_USERNAME: "",
                CONF_PASSWORD: "",
                CONF_INSTALLATION_ID: "",
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=user_input[CONF_NAME]): str,
                    vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                    vol.Required(
                        CONF_INSTALLATION_ID, default=user_input[CONF_INSTALLATION_ID]
                    ): int,
                }
            ),
            errors=self._errors,
        )
