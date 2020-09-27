"""Hyperion config flow."""

import logging
from typing import Any, Dict, Optional

from hyperion import client, const
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.typing import ConfigType

from .const import CONF_CREATE_TOKEN, CONF_INSTANCE, DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)


class HyperionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hyperion config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Instantiate config flow."""
        super().__init__()
        self._data: Optional[Dict[str, Any]] = None

    async def _create_and_connect_hyperion_client(
        self, raw=False
    ) -> Optional[client.HyperionClient]:
        """Create and connect a client instance."""
        if self._data is None:
            return
        hc = client.HyperionClient(
            self._data[CONF_HOST],
            self._data[CONF_PORT],
            token=self._data.get(CONF_TOKEN),
            instance=self._data[CONF_INSTANCE],
        )
        if await hc.async_client_connect(raw=raw):
            return hc

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if not user_input:
            return self._show_setup_form()
        self._data = user_input

        # First connect without attempting to login or select instance,
        # and determine if authentication is required.
        hc = await self._create_and_connect_hyperion_client(raw=True)
        if not hc:
            return self._show_setup_form({CONF_BASE: "connection_error"})

        hyperion_id = hc.id
        auth_resp = await hc.async_is_auth_required()
        await hc.async_client_disconnect()

        await self.async_set_unique_id(hyperion_id)
        self._abort_if_unique_id_configured()

        # Could not determine if auth is required, show error.
        if not client.ResponseOK(auth_resp):
            return self._show_setup_form({CONF_BASE: "auth_required_error"})

        if auth_resp.get(const.KEY_INFO, {}).get(const.KEY_REQUIRED) is True:
            # Auth is required, show the form to get the token.
            return self._show_auth_form()

        # Reconnect in non-raw mode (will attempt to load state). Verify
        # everything is okay, and create the entry if so.
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_setup_form({CONF_BASE: "connection_error"})
        await hc.async_client_disconnect()

        return self.async_create_entry(title=self.context["unique_id"], data=self._data)

    async def async_step_auth(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle the auth step of a flow."""
        if not user_input:
            return self._show_auth_form()

        _LOGGER.error("Auth called with %s", user_input)

        if user_input.get(CONF_CREATE_TOKEN):
            # TODO
            assert False
            return

        self._data[CONF_TOKEN] = user_input.get(CONF_TOKEN)
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_setup_form({CONF_BASE: "auth_error"})
        return self.async_create_entry(title=self.context["unique_id"], data=self._data)

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=const.DEFAULT_PORT): int,
                    vol.Optional(CONF_INSTANCE, default=const.DEFAULT_INSTANCE): int,
                }
            ),
            errors=errors or {},
        )

    def _show_auth_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the auth form to the user."""
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CREATE_TOKEN): bool,
                    vol.Optional(CONF_TOKEN): str,
                }
            ),
            errors=errors or {},
        )
