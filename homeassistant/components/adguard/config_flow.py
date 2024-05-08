"""Config flow to configure the AdGuard Home integration."""

from __future__ import annotations

from typing import Any

from adguardhome import AdGuardHome, AdGuardHomeConnectionError
import voluptuous as vol

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class AdGuardHomeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a AdGuard Home config flow."""

    VERSION = 1

    _hassio_discovery: dict[str, Any] | None = None

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=3000): vol.Coerce(int),
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL, default=True): bool,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors or {},
        )

    async def _show_hassio_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the Hass.io confirmation form to the user."""
        assert self._hassio_discovery
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
        )

        errors = {}

        session = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])

        username: str | None = user_input.get(CONF_USERNAME)
        password: str | None = user_input.get(CONF_PASSWORD)
        adguard = AdGuardHome(
            user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            username=username,
            password=password,
            tls=user_input[CONF_SSL],
            verify_ssl=user_input[CONF_VERIFY_SSL],
            session=session,
        )

        try:
            await adguard.version()
        except AdGuardHomeConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)

        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
                CONF_PORT: user_input[CONF_PORT],
                CONF_SSL: user_input[CONF_SSL],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
            },
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a Hass.io AdGuard Home add-on.

        This flow is triggered by the discovery component.
        """
        await self._async_handle_discovery_without_unique_id()

        self._hassio_discovery = discovery_info.config
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery."""
        if user_input is None:
            return await self._show_hassio_form()

        errors = {}

        session = async_get_clientsession(self.hass, False)

        assert self._hassio_discovery
        adguard = AdGuardHome(
            self._hassio_discovery[CONF_HOST],
            port=self._hassio_discovery[CONF_PORT],
            tls=False,
            session=session,
        )

        try:
            await adguard.version()
        except AdGuardHomeConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_hassio_form(errors)

        return self.async_create_entry(
            title=self._hassio_discovery["addon"],
            data={
                CONF_HOST: self._hassio_discovery[CONF_HOST],
                CONF_PORT: self._hassio_discovery[CONF_PORT],
                CONF_PASSWORD: None,
                CONF_SSL: False,
                CONF_USERNAME: None,
                CONF_VERIFY_SSL: True,
            },
        )
