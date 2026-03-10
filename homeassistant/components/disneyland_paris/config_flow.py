"""Config flow for Disneyland Paris Integration."""

from typing import Any

from dlpwait import DLPWaitAPI, DLPWaitError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class DisneylandParisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Config Flow for Disneyland Paris."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Initial Setup."""

        errors: dict[str, str] = {}

        if user_input is not None:
            connection = await self._validate_connection()
            if connection:
                return self.async_create_entry(title="Disneyland Paris", data={})

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            errors=errors,
        )

    async def _validate_connection(self) -> bool:
        """Try to fetch park data to confirm the Disneyland Paris service is working."""

        client = DLPWaitAPI(async_get_clientsession(self.hass))

        try:
            await client.update()
        except DLPWaitError:
            return False

        return True
