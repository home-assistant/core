"""Hyperion config flow."""

import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from hyperion import client, const
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.const import CONF_BASE, CONF_HOST, CONF_ID, CONF_PORT, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType

# pylint: disable=unused-import
from .const import (
    CONF_AUTH_ID,
    CONF_CREATE_TOKEN,
    CONF_HYPERION_URL,
    CONF_PRIORITY,
    DEFAULT_ORIGIN,
    DEFAULT_PRIORITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

#     +-----------------------+
#     |Step: SSDP             |
# --->|                       |
#     |Input: <discovery data>|
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

# A note on choice of discovery mechanisms: Hyperion supports both Zeroconf and SSDP out
# of the box. This config flow needs two port numbers from the Hyperion instance, the
# JSON port (for the API) and the UI port (for the user to approve dynamically created
# auth tokens). With Zeroconf the port numbers for both are in different Zeroconf
# entries, and as Home Assistant only passes a single entry into the config flow, we can
# only conveniently 'see' one port or the other (which means we need to guess one port
# number). With SSDP, we get the combined block including both port numbers, so SSDP is
# the favored discovery implementation.


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
        self._port_ui = const.DEFAULT_PORT_UI

    async def _create_client(
        self, raw_connection=False
    ) -> Optional[client.HyperionClient]:
        """Create and connect a client instance."""
        return client.HyperionClient(
            self._data[CONF_HOST],
            self._data[CONF_PORT],
            token=self._data.get(CONF_TOKEN),
            raw_connection=raw_connection,
        )

    async def async_step_import(
        self, import_data: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by a YAML config import."""
        self._auto_confirm = True
        return await self.async_step_user(user_input=import_data)

    async def async_step_ssdp(
        self, discovery_info: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle a flow initiated by SSDP."""
        # Sample data provided by SSDP: {
        #   'ssdp_location': 'http://192.168.0.1:8090/description.xml',
        #   'ssdp_st': 'upnp:rootdevice',
        #   'deviceType': 'urn:schemas-upnp-org:device:Basic:1',
        #   'friendlyName': 'Hyperion (192.168.0.1)',
        #   'manufacturer': 'Hyperion Open Source Ambient Lighting',
        #   'manufacturerURL': 'https://www.hyperion-project.org',
        #   'modelDescription': 'Hyperion Open Source Ambient Light',
        #   'modelName': 'Hyperion',
        #   'modelNumber': '2.0.0-alpha.8',
        #   'modelURL': 'https://www.hyperion-project.org',
        #   'serialNumber': 'f9aab089-f85a-55cf-b7c1-222a72faebe9',
        #   'UDN': 'uuid:f9aab089-f85a-55cf-b7c1-222a72faebe9',
        #   'ports': {
        #       'jsonServer': '19444',
        #       'sslServer': '8092',
        #       'protoBuffer': '19445',
        #       'flatBuffer': '19400'
        #   },
        #   'presentationURL': 'index.html',
        #   'iconList': {
        #       'icon': {
        #           'mimetype': 'image/png',
        #           'height': '100',
        #           'width': '100',
        #           'depth': '32',
        #           'url': 'img/hyperion/ssdp_icon.png'
        #       }
        #   },
        #   'ssdp_usn': 'uuid:f9aab089-f85a-55cf-b7c1-222a72faebe9',
        #   'ssdp_ext': '',
        #   'ssdp_server': 'Raspbian GNU/Linux 10 (buster)/10 UPnP/1.0 Hyperion/2.0.0-alpha.8'}
        data = {}

        data[CONF_HOST] = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        self._port_ui = urlparse(discovery_info[ATTR_SSDP_LOCATION]).port

        try:
            data[CONF_PORT] = int(
                discovery_info.get("ports", {}).get(
                    "jsonServer", const.DEFAULT_PORT_JSON
                )
            )
        except ValueError:
            data[CONF_PORT] = const.DEFAULT_PORT_JSON

        hyperion_id = discovery_info.get(ATTR_UPNP_SERIAL)
        if hyperion_id:
            # For discovery mechanisms, we set the unique_id as early as possible to
            # avoid discovery popping up a duplicate on the screen. The unique_id is set
            # authoritatively later in the flow by asking the server to confirm its id
            # (which should theoretically be the same as specified here)
            await self.async_set_unique_id(hyperion_id)
            self._abort_if_unique_id_configured()
        else:
            return self.async_abort(reason="no_id")
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
        async with await self._create_client(raw_connection=True) as hyperion_client:
            if not hyperion_client:
                return self._show_setup_form({CONF_BASE: "connection_error"})
            auth_resp = await hyperion_client.async_is_auth_required()

        # Could not determine if auth is required, show error.
        if not client.ResponseOK(auth_resp):
            return self._show_setup_form({CONF_BASE: "auth_required_error"})

        if auth_resp.get(const.KEY_INFO, {}).get(const.KEY_REQUIRED) is True:
            # Auth is required, show the form to get the token.
            return self._show_auth_form()
        return await self._show_confirm_form()

    async def _cancel_request_token_task(self) -> None:
        """Cancel the request token task if it exists."""
        if self._request_token_task is not None:
            if not self._request_token_task.done():
                self._request_token_task.cancel()

            # Cancellation is only processed on the **next** cycle of the event loop, so
            # yield here.
            await asyncio.sleep(0)

            try:
                await self._request_token_task
            except asyncio.CancelledError:
                pass
            self._request_token_task = None

    async def _request_token_task_func(self, auth_id: str) -> Optional[ConfigType]:
        """Send an async_request_token request."""
        auth_resp = {}
        async with await self._create_client(raw_connection=True) as hyperion_client:
            if hyperion_client:
                # The Hyperion-py client has a default timeout of 3 minutes on this request.
                auth_resp = await hyperion_client.async_request_token(
                    comment=DEFAULT_ORIGIN, id=auth_id
                )
            await self.hass.config_entries.flow.async_configure(
                flow_id=self.flow_id, user_input=auth_resp
            )
        return auth_resp

    def _get_hyperion_url(self):
        """Return the URL of the Hyperion UI."""
        # If this flow was kicked off by SSDP, this will be the correct frontend URL. If
        # this is a manual flow instantiation, then it will be a best guess (as this
        # flow does not have that information available to it). This is only used for
        # approving new dynamically created tokens, so the complexity of asking the user
        # manually for this information is likely not worth it (when it would only be
        # used to open a URL, that the user already knows the address of).
        return f"http://{self._data[CONF_HOST]}:{self._port_ui}"

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

        async with await self._create_client() as hyperion_client:
            if not hyperion_client:
                return self._show_auth_form({CONF_BASE: "auth_error"})
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
        self, auth_resp: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Handle completion of the request for a new token."""
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
        # Clean-up the request task.
        await self._cancel_request_token_task()

        # Test the token.
        async with await self._create_client() as hyperion_client:
            if not hyperion_client:
                return self._show_auth_form(
                    {CONF_BASE: "auth_new_token_not_work_error"}
                )
        return await self._show_confirm_form()

    async def async_step_create_token_fail(
        self, _: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Show an error on the auth form."""
        # Clean-up the request task.
        await self._cancel_request_token_task()
        return self._show_auth_form({CONF_BASE: "auth_new_token_not_granted_error"})

    async def async_step_confirm(
        self, user_input: Optional[ConfigType] = None
    ) -> Dict[str, Any]:
        """Get final confirmation before entry creation."""
        if user_input is None and not self._auto_confirm:
            return await self._show_confirm_form()

        # pylint: disable=no-member  # https://github.com/PyCQA/pylint/issues/3167
        return self.async_create_entry(
            title=f"{self._data[CONF_HOST]}:{self._data[CONF_PORT]}", data=self._data
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
        async with await self._create_client() as hyperion_client:
            if not hyperion_client:
                return self._show_setup_form({CONF_BASE: "connection_error"})
            hyperion_id = await hyperion_client.async_id()

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the Hyperion Options flow."""
        return HyperionOptionsFlow(config_entry)


class HyperionOptionsFlow(config_entries.OptionsFlow):
    """Hyperion options flow."""

    def __init__(self, config_entry):
        """Initialize a Hyperion options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PRIORITY,
                        default=self._config_entry.options.get(
                            CONF_PRIORITY, DEFAULT_PRIORITY
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
                }
            ),
        )
