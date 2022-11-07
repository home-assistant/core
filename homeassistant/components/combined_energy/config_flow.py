"""Config flow for Combined Energy integration."""
from __future__ import annotations

import logging
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

_LOGGER = logging.getLogger(__name__)


class CombinedEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Combined Energy."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._errors: dict[str, str] = {}

    def _current_installation_ids(self) -> set[int]:
        """Return the installation ids for the domain."""
        return {
            entry.data[CONF_INSTALLATION_ID]
            for entry in self._async_current_entries(include_ignore=False)
            if CONF_INSTALLATION_ID in entry.data
        }

    def _installation_exists_in_configuration(self, installation_id: int) -> bool:
        """Determine if installation already exists in configuration."""
        return installation_id in self._current_installation_ids()

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
            self._errors[CONF_USERNAME] = "invalid_auth"
        except CombinedEnergyPermissionError:
            self._errors[CONF_INSTALLATION_ID] = "installation_not_accessible"
        except CombinedEnergyTimeoutError:
            self._errors[CONF_USERNAME] = "cannot_connect"
        except CombinedEnergyError:
            LOGGER.exception("Unexpected error verifying connection to API")
            self._errors[CONF_INSTALLATION_ID] = "cannot_connect"
        else:
            return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._errors = {}

        if user_input is not None:
            if self._installation_exists_in_configuration(
                user_input[CONF_INSTALLATION_ID]
            ):
                self._errors[CONF_INSTALLATION_ID] = "already_configured"
            else:
                username = user_input[CONF_USERNAME]
                password = user_input[CONF_PASSWORD]
                installation_id = user_input[CONF_INSTALLATION_ID]
                can_connect = await self._check_installation(
                    username, password, installation_id
                )
                if can_connect:
                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME, DEFAULT_NAME),
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_INSTALLATION_ID: user_input[CONF_INSTALLATION_ID],
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
            description_placeholders={},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(CONF_USERNAME, default=user_input[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD, default=user_input[CONF_PASSWORD]): str,
                    vol.Required(
                        CONF_INSTALLATION_ID, default=user_input[CONF_INSTALLATION_ID]
                    ): int,
                }
            ),
            errors=self._errors,
        )
