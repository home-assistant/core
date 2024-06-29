"""Config flow for dio_chacon integration."""

from __future__ import annotations

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient
from dio_chacon_wifi_api.exceptions import DIOChaconAPIError, DIOChaconInvalidAuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class DioChaconConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dio_chacon."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the user name and password and retrieve the technical user id.
            client = DIOChaconAPIClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            try:
                _user_id: str = await client.get_user_id()
            except DIOChaconAPIError:
                errors["base"] = "cannot_connect"
            except DIOChaconInvalidAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                # Check if already configured
                await self.async_set_unique_id(_user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Dio Chacon {user_input[CONF_USERNAME]}",
                    data=user_input,
                )

            finally:
                await client.disconnect()

        # User input is None or an error happened, show the form to the user.
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
