"""Config flow for Aussie Broadband integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError
from aussiebb.asyncio import AussieBB, AuthenticationException
from aussiebb.const import FETCH_TYPES
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SERVICES, DOMAIN


class AussieBroadbandConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aussie Broadband."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict = {}
        self.options: dict = {CONF_SERVICES: []}
        self.services: list[dict[str, Any]] = []
        self.client: AussieBB | None = None
        self._reauth_username: str | None = None

    async def async_auth(self, user_input: dict[str, str]) -> dict[str, str] | None:
        """Reusable Auth Helper."""
        self.client = AussieBB(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            async_get_clientsession(self.hass),
        )
        try:
            await self.client.login()
        except AuthenticationException:
            return {"base": "invalid_auth"}
        except ClientError:
            return {"base": "cannot_connect"}
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            if not (errors := await self.async_auth(user_input)):
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                self.data = user_input
                self.services = await self.client.get_services(drop_types=FETCH_TYPES)  # type: ignore[union-attr]

                if not self.services:
                    return self.async_abort(reason="no_services_found")

                return self.async_create_entry(
                    title=self.data[CONF_USERNAME],
                    data=self.data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth on credential failure."""
        self._reauth_username = entry_data[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle users reauth credentials."""

        errors: dict[str, str] | None = None

        if user_input and self._reauth_username:
            data = {
                CONF_USERNAME: self._reauth_username,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            if not (errors := await self.async_auth(data)):
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                assert entry
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"username": self._reauth_username},
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
