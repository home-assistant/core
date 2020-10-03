"""Hyperion config flow."""

import asyncio
import logging
from typing import Any, Dict, Optional

from hyperion import client, const
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTH_ID,
    CONF_CREATE_TOKEN,
    CONF_HYPERION_URL,
    CONF_INSTANCE,
    DEFAULT_ORIGIN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

#     +----------------+
#     |Step: user      |
#     |                |
#     |Input: host/port|
#     +----------------+
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
#   +---------------+           |
#   |Form: Instance |           |
#   |               |<----------+
#   |Input: instance|
#   +---------------+
#           |
#           v
#   +---------------+
#   |Step: Final    |
#   +---------------+


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
            instance=self._data.get(CONF_INSTANCE, const.DEFAULT_INSTANCE),
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
        auth_resp = await hc.async_is_auth_required()
        await hc.async_client_disconnect()

        # Could not determine if auth is required, show error.
        if not client.ResponseOK(auth_resp):
            return self._show_setup_form({CONF_BASE: "auth_required_error"})

        if auth_resp.get(const.KEY_INFO, {}).get(const.KEY_REQUIRED) is True:
            # Auth is required, show the form to get the token.
            return self._show_auth_form()
        return await self._show_instance_form_if_necessary()

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
        return f"http://{self._data[CONF_HOST]}:{const.DEFAULT_PORT_UI}"

    async def async_step_auth(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle the auth step of a flow."""
        if not user_input:
            return self._show_auth_form()

        if user_input.get(CONF_CREATE_TOKEN):
            # TODO: See if the UI port can be taken from Zeroconf?
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
        return await self._show_instance_form_if_necessary()

    async def async_step_create_token(
        self, user_input: Optional[ConfigType] = None
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
        self, user_input: Optional[ConfigType] = None
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
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Create an entry after successful token creation."""
        # Test the token.
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_auth_form({CONF_BASE: "auth_new_token_not_work_error"})
        await hc.async_client_disconnect()
        return await self._show_instance_form_if_necessary()

    async def async_step_create_token_fail(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Show an error on the auth form."""
        return self._show_auth_form({CONF_BASE: "auth_new_token_not_granted_error"})

    async def async_step_final(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Show the instance form if necessary."""
        self._data[CONF_INSTANCE] = self._instances[user_input.get(CONF_INSTANCE)]

        # Test a full connection.
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return await self._show_instance_form_if_necessary(
                {CONF_BASE: "instance_error"}
            )
        hyperion_id = hc.id
        await hc.async_client_disconnect()

        await self.async_set_unique_id(hyperion_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=self.context["unique_id"], data=self._data)

    async def async_step_zeroconf(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by zeroconf."""
        _LOGGER.error("Zeroconf %s", user_input)
        # Hostname is format: hyperion.local.
        data = {}
        data[CONF_HOST] = user_input["hostname"].rstrip(".")
        data[CONF_PORT] = user_input["port"]
        # data[const.KEY_NAME] = data[CONF_HOST].rsplit(".")[0]
        # data[const.KEY_ID] = user_input["properties"]["id"]

        return await self.async_step_user(user_input=data)

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

    async def _show_instance_form_if_necessary(
        self, errors: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Show the instance form to the user."""
        hc = await self._create_and_connect_hyperion_client()
        if not hc:
            return self._show_setup_form({CONF_BASE: "connection_error"})
        self._instances = {}
        for instance in hc.instances:
            if (
                instance.get(const.KEY_RUNNING, False)
                and const.KEY_FRIENDLY_NAME in instance
                and const.KEY_INSTANCE in instance
            ):
                self._instances[instance.get(const.KEY_FRIENDLY_NAME)] = instance.get(
                    const.KEY_INSTANCE
                )
        await hc.async_client_disconnect()

        if not self._instances:
            return self.async_abort(reason="no_running_instances")
        elif len(self._instances) > 1:
            return self.async_show_form(
                step_id="final",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_INSTANCE): vol.In(
                            list(self._instances.keys())
                        ),
                    }
                ),
            )
        return await self.async_step_final(
            user_input={CONF_INSTANCE: next(iter(self._instances.keys()))}
        )
