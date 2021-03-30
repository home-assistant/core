"""Config flow to configure the AdGuard Home integration."""
from __future__ import annotations

from typing import Any

from adguardhome import AdGuardHome, AdGuardHomeConnectionError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
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
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    _hassio_discovery = None

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
        """Show the Hass.io confirmation form to the user."""
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"addon": self._hassio_discovery["addon"]},
            data_schema=vol.Schema({}),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle a flow initiated by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}

        session = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])

        adguard = AdGuardHome(
            user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
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

    async def async_step_hassio(self, discovery_info: dict[str, Any]) -> dict[str, Any]:
        """Prepare configuration for a Hass.io AdGuard Home add-on.

        This flow is triggered by the discovery component.
        """
        entries = self._async_current_entries()

        if not entries:
            self._hassio_discovery = discovery_info
            await self._async_handle_discovery_without_unique_id()
            return await self.async_step_hassio_confirm()

        cur_entry = entries[0]

        if (
            cur_entry.data[CONF_HOST] == discovery_info[CONF_HOST]
            and cur_entry.data[CONF_PORT] == discovery_info[CONF_PORT]
        ):
            return self.async_abort(reason="single_instance_allowed")

        is_loaded = cur_entry.state == config_entries.ENTRY_STATE_LOADED

        if is_loaded:
            await self.hass.config_entries.async_unload(cur_entry.entry_id)

        self.hass.config_entries.async_update_entry(
            cur_entry,
            data={
                **cur_entry.data,
                CONF_HOST: discovery_info[CONF_HOST],
                CONF_PORT: discovery_info[CONF_PORT],
            },
        )

        if is_loaded:
            await self.hass.config_entries.async_setup(cur_entry.entry_id)

        return self.async_abort(reason="existing_instance_updated")

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Confirm Hass.io discovery."""
        if user_input is None:
            return await self._show_hassio_form()

        errors = {}

        session = async_get_clientsession(self.hass, False)

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
