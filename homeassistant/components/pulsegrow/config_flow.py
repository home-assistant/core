"""Config flow for PulseGrow integration."""

from __future__ import annotations

from typing import Any

from aiopulsegrow import PulsegrowClient, PulsegrowError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class PulseGrowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PulseGrow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = PulsegrowClient(
                user_input[CONF_API_KEY],
                session=async_get_clientsession(self.hass),
            )

            try:
                users = await client.get_users()
            except PulsegrowError as err:
                LOGGER.debug("Failed to connect to PulseGrow API: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error during PulseGrow setup")
                errors["base"] = "unknown"
            else:
                # Use first user from the list (API returns users with access)
                user = users[0]
                await self.async_set_unique_id(str(user.user_id))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user.user_name or "PulseGrow",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
