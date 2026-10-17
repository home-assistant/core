"""Pair Terrestream using the code on its display."""

from dataclasses import asdict
from typing import Any, override

import probatio
from terrestream_local import pair_device
from terrestream_local.errors import AuthenticationError, ClientError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class TerrestreamConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one physically authorized sensor."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate pairing and prevent duplicate sensor entries."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                credentials, _client = await pair_device(
                    async_get_clientsession(self.hass),
                    user_input["host"],
                    user_input["code"],
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ClientError, ValueError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(credentials.uuid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Terrestream",
                    data={
                        "host": user_input["host"],
                        "credentials": asdict(credentials),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required("host"): str, probatio.Required("code"): str}
            ),
            errors=errors,
        )
