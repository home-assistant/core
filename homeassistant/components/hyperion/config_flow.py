"""Hyperion config flow."""

import asyncio
import logging
from typing import Any, Dict, Optional

from hyperion import client, const
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_ID,
    CONF_PORT,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTH_ID,
    CONF_CREATE_TOKEN,
    CONF_HYPERION_URL,
    DEFAULT_ORIGIN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

#     +-----------------------+
#     |Step: Zeroconf         |
# --->|                       |
#     |Input: <zeroconf data> |
#     +-----------------------+
#           |
#           |
#           v
#     +----------------+    +--------------------+
#     |Step: user      |    |Step: import        |
# --->|                |<---|                    |<---
#     |Input: host/port|    |Input: <import data>|
#     +----------------+    +--------------------+
#           |
#           |    Auth        +------------+
#           |    required?   |Step: auth  |
#           +--------------->|            |
# Auth not  |                |Input: token|
# required? |                +------------+
#           |    Static         |
#           v    token?         |
#            <------------------+
#           |                   |
#           |                   |New token?
#           |                   v
#           |            +------------------+
#           |            |Step: create_token|
#           |            +------------------+
#           |                   |
#           |                   v
#           |            +---------------------------+   +--------------------------------+
#           |            |Step: create_token_external|-->|Step: create_token_external_fail|
#           |            +---------------------------+   +--------------------------------+
#           |                   |
#           |                   v
#           |            +-----------------------------------+
#           |            |Step: create_token_external_success|
#           |            +-----------------------------------+
#           |                   |
#           v                   |
#     +----------------+        |
#     | Step: Confirm  |<-------+
#     +----------------+
#           |
#           v
#     +----------------+
#     |    Create!     |
#     +----------------+


class HyperionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hyperion config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Instantiate config flow."""
        super().__init__()
        self._data: Optional[Dict[str, Any]] = None
        self._request_token_task = None
        self._auth_id = None
        self._auto_confirm = False

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
        )
        if await hc.async_client_connect(raw=raw):
            return hc

    async def async_step_import(
        self, import_data: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by a YAML config import."""
        self._auto_confirm = True
        return await self.async_step_user(user_input=import_data)

    async def async_step_zeroconf(
        self, discovery_info: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""

        # Sample data provided by Zeroconf: {
        #   'host': '192.168.0.1',
        #   'port': 19444,
        #   'hostname': 'hyperion.local.',
        #   'type': '_hyperiond-json._tcp.local.',
        #   'name': 'hyperion:19444._hyperiond-json._tcp.local.',
        #   'properties': {
        #     '_raw': {
        #       'id': b'f9aab089-f85a-55cf-b7c1-222a72faebe9',
        #       'version': b'2.0.0-alpha.8'},
        #     'id': 'f9aab089-f85a-55cf-b7c1-222a72faebe9',
        #     'version': '2.0.0-alpha.8'}}
        data = {}

        # Intentionally uses the IP address field, as ".local" cannot
        # be resolved by Home Assistant Core in Docker.
        # See related: https://github.com/home-assistant/core/issues/38537
        data[CONF_HOST] = discovery_info["host"]
        data[CONF_PORT] = discovery_info["port"]
        # data[const.KEY_NAME] = data[CONF_HOST].rsplit(".")[0]
        # data[const.KEY_ID] = user_input["properties"]["id"]

        return await self.async_step_user(user_input=data)

    async def async_step_user(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by the user."""
        if not user_input:
            return self._show_setup_form()
        self._data = user_input

        # First connect without attempting to login and determine if
        # authentication is required.
        hc = await self._create_and_connect_hyperion_client(raw=True)
        if not hc:
            return self._show_setup_form({CONF_BASE: "connection_error"})
        auth_resp = await hc.async_is_auth_required()
        await hc.async_client_disconnect()

        # Could not determine if auth is required, show error.
        if not client.ResponseOK(auth_resp):
            return self._show_setup_form({CONF_BASE: "auth_required_error"})

        if auth_resp.get(const.KEY_INFO, {}).get(const.KEY_REQUIRED) is True:
            # Auth is required, show the form to get the token.
            return self._show_auth_form()

        # Test a full connection with state load.
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_setup_form({CONF_BASE: "connection_error"})
        await hc.async_client_disconnect()

        return await self._show_confirm_form()

    async def _cancel_request_token_task(self) -> None:
        """Cancel the request token task if it exists."""
        if self._request_token_task is not None:
            if not self._request_token_task.done():
                self._request_token_task.cancel()

            # Process cancellation.
            await asyncio.sleep(0)

            try:
                await self._request_token_task
            except asyncio.CancelledError:
                pass
            self._request_token_task = None

    async def _request_token_task_func(self, auth_id: str) -> Dict[str, Any]:
        """Send an async_request_token request."""
        hc = await self._create_and_connect_hyperion_client(raw=True)
        if hc:
            # The Hyperion-py client has a default timeout of 3 minutes on this request.
            response = await hc.async_request_token(comment=DEFAULT_ORIGIN, id=auth_id)
            await hc.async_client_disconnect()
            return response
        return None

    def _get_hyperion_url(self):
        """Return the URL of the Hyperion UI."""
        # This is a guess at the web frontend URL for this client. We have no
        # way of knowing that it is correct. Alternatives may be ask the user
        # for the http port, to listen on zeroconf (we already have the JSON
        # port, but not the http port), or to ask Hyperion via JSON for the
        # network sessions.  However, as it is only used for approving new
        # tokens, and as the user can just open it manually, the extra
        # complexity may not be worth it.
        return f"http://{self._data[CONF_HOST]}:{const.DEFAULT_PORT_UI}"

    async def async_step_auth(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle the auth step of a flow."""
        if not user_input:
            return self._show_auth_form()

        if user_input.get(CONF_CREATE_TOKEN):
            self._auth_id = client.generate_random_auth_id()
            return self.async_show_form(
                step_id="create_token",
                description_placeholders={
                    CONF_AUTH_ID: self._auth_id,
                    CONF_HYPERION_URL: self._get_hyperion_url(),
                },
            )

        self._data[CONF_TOKEN] = user_input.get(CONF_TOKEN)
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_auth_form({CONF_BASE: "auth_error"})
        await hc.async_client_disconnect()
        return await self._show_confirm_form()

    async def async_step_create_token(
        self, _: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Send a request for a new token."""
        # Cancel the request token task if it's already running, then re-create it.
        await self._cancel_request_token_task()
        # Start a task in the background requesting a new token. The next step will
        # wait on the response (which includes the user needing to visit the Hyperion
        # UI to approve the request for a new token).
        self._request_token_task = self.hass.async_create_task(
            self._request_token_task_func(self._auth_id)
        )
        return self.async_external_step(
            step_id="create_token_external", url=self._get_hyperion_url()
        )

    async def async_step_create_token_external(
        self, _: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Await completion of the request for a new token."""
        if self._request_token_task:
            auth_resp = await self._request_token_task
            if client.ResponseOK(auth_resp):
                token = auth_resp.get(const.KEY_INFO, {}).get(const.KEY_TOKEN)
                if token:
                    self._data[CONF_TOKEN] = token
                    return self.async_external_step_done(
                        next_step_id="create_token_success"
                    )
        return self.async_external_step_done(next_step_id="create_token_fail")

    async def async_step_create_token_success(
        self, _: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Create an entry after successful token creation."""
        # Test the token.
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_auth_form({CONF_BASE: "auth_new_token_not_work_error"})
        await hc.async_client_disconnect()
        return await self._show_confirm_form()

    async def async_step_create_token_fail(
        self, _: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Show an error on the auth form."""
        return self._show_auth_form({CONF_BASE: "auth_new_token_not_granted_error"})

    async def async_step_confirm(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Get final confirmation before entry creation."""
        if user_input is None and not self._auto_confirm:
            return await self._show_confirm_form()

        return self.async_create_entry(
            title=self.context[CONF_UNIQUE_ID], data=self._data
        )

    def _show_setup_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=const.DEFAULT_PORT_JSON): int,
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

    async def _show_confirm_form(self, errors: Optional[Dict] = None) -> Dict[str, Any]:
        """Show the confirmation form to the user."""
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_setup_form({CONF_BASE: "connection_error"})
        hyperion_id = await hc.async_id()
        await hc.async_client_disconnect()

        if not hyperion_id:
            return self.async_abort(reason="no_id")

        await self.async_set_unique_id(hyperion_id)
        self._abort_if_unique_id_configured()

        if self._auto_confirm:
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                CONF_HOST: self._data[CONF_HOST],
                CONF_PORT: self._data[CONF_PORT],
                CONF_ID: self.unique_id,
            },
        )
