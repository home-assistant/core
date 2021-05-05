"""Hyperion config flow."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import Any
from urllib.parse import urlparse

from hyperion import client, const
import voluptuous as vol

from homeassistant.components.ssdp import ATTR_SSDP_LOCATION, ATTR_UPNP_SERIAL
from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_PUSH,
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_ID,
    CONF_PORT,
    CONF_SOURCE,
    CONF_TOKEN,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import create_hyperion_client
from .const import (
    CONF_AUTH_ID,
    CONF_CREATE_TOKEN,
    CONF_EFFECT_HIDE_LIST,
    CONF_EFFECT_SHOW_LIST,
    CONF_PRIORITY,
    DEFAULT_ORIGIN,
    DEFAULT_PRIORITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

#  +------------------+ +------------------+ +--------------------+ +--------------------+
#  |Step: SSDP        | |Step: user        | |Step: import        | |Step: reauth        |
#  |                  | |                  | |                    | |                    |
#  |Input: <discovery>| |Input: <host/port>| |Input: <import data>| |Input: <entry_data> |
#  +------------------+ +------------------+ +--------------------+ +--------------------+
#           v                   v                       v                    v
#           +-------------------+-----------------------+--------------------+
# Auth not  |         Auth      |
# required? |         required? |
#           |                   v
#           |                +------------+
#           |                |Step: auth  |
#           |                |            |
#           |                |Input: token|
#           |                +------------+
#           |    Static         |
#           v    token          |
#            <------------------+
#           |                   |
#           |                   | New token
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
#           v<------------------+
#           |
#           v
#     +-------------+  Confirm not required?
#     |Step: Confirm|---------------------->+
#     +-------------+                       |
#           |                               |
#           v SSDP: Explicit confirm        |
#           +------------------------------>+
#                                           |
#                                           v
#                                 +----------------+
#                                 | Create/Update! |
#                                 +----------------+

# A note on choice of discovery mechanisms: Hyperion supports both Zeroconf and SSDP out
# of the box. This config flow needs two port numbers from the Hyperion instance, the
# JSON port (for the API) and the UI port (for the user to approve dynamically created
# auth tokens). With Zeroconf the port numbers for both are in different Zeroconf
# entries, and as Home Assistant only passes a single entry into the config flow, we can
# only conveniently 'see' one port or the other (which means we need to guess one port
# number). With SSDP, we get the combined block including both port numbers, so SSDP is
# the favored discovery implementation.


class HyperionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Hyperion config flow."""

    VERSION = 1
    CONNECTION_CLASS = CONN_CLASS_LOCAL_PUSH

    def __init__(self) -> None:
        """Instantiate config flow."""
        self._data: dict[str, Any] = {}
        self._request_token_task: asyncio.Task | None = None
        self._auth_id: str | None = None
        self._require_confirm: bool = False
        self._port_ui: int = const.DEFAULT_PORT_UI

    def _create_client(self, raw_connection: bool = False) -> client.HyperionClient:
        """Create and connect a client instance."""
        return create_hyperion_client(
            self._data[CONF_HOST],
            self._data[CONF_PORT],
            token=self._data.get(CONF_TOKEN),
            raw_connection=raw_connection,
        )

    async def _advance_to_auth_step_if_necessary(
        self, hyperion_client: client.HyperionClient
    ) -> FlowResult:
        """Determine if auth is required."""
        auth_resp = await hyperion_client.async_is_auth_required()

        # Could not determine if auth is required.
        if not auth_resp or not client.ResponseOK(auth_resp):
            return self.async_abort(reason="auth_required_error")
        auth_required = auth_resp.get(const.KEY_INFO, {}).get(const.KEY_REQUIRED, False)
        if auth_required:
            return await self.async_step_auth()
        return await self.async_step_confirm()

    async def async_step_reauth(
        self,
        config_data: ConfigType,
    ) -> FlowResult:
        """Handle a reauthentication flow."""
        self._data = dict(config_data)
        async with self._create_client(raw_connection=True) as hyperion_client:
            if not hyperion_client:
                return self.async_abort(reason="cannot_connect")
            return await self._advance_to_auth_step_if_necessary(hyperion_client)

    async def async_step_ssdp(self, discovery_info: dict[str, Any]) -> FlowResult:
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

        # SSDP requires user confirmation.
        self._require_confirm = True
        self._data[CONF_HOST] = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        try:
            self._port_ui = urlparse(discovery_info[ATTR_SSDP_LOCATION]).port
        except ValueError:
            self._port_ui = const.DEFAULT_PORT_UI

        try:
            self._data[CONF_PORT] = int(
                discovery_info.get("ports", {}).get(
                    "jsonServer", const.DEFAULT_PORT_JSON
                )
            )
        except ValueError:
            self._data[CONF_PORT] = const.DEFAULT_PORT_JSON

        hyperion_id = discovery_info.get(ATTR_UPNP_SERIAL)
        if not hyperion_id:
            return self.async_abort(reason="no_id")

        # For discovery mechanisms, we set the unique_id as early as possible to
        # avoid discovery popping up a duplicate on the screen. The unique_id is set
        # authoritatively later in the flow by asking the server to confirm its id
        # (which should theoretically be the same as specified here)
        await self.async_set_unique_id(hyperion_id)
        self._abort_if_unique_id_configured()

        async with self._create_client(raw_connection=True) as hyperion_client:
            if not hyperion_client:
                return self.async_abort(reason="cannot_connect")
            return await self._advance_to_auth_step_if_necessary(hyperion_client)

    async def async_step_user(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input:
            self._data.update(user_input)

            async with self._create_client(raw_connection=True) as hyperion_client:
                if hyperion_client:
                    return await self._advance_to_auth_step_if_necessary(
                        hyperion_client
                    )
                errors[CONF_BASE] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=const.DEFAULT_PORT_JSON): int,
                }
            ),
            errors=errors,
        )

    async def _cancel_request_token_task(self) -> None:
        """Cancel the request token task if it exists."""
        if self._request_token_task is not None:
            if not self._request_token_task.done():
                self._request_token_task.cancel()

            with suppress(asyncio.CancelledError):
                await self._request_token_task
            self._request_token_task = None

    async def _request_token_task_func(self, auth_id: str) -> None:
        """Send an async_request_token request."""
        auth_resp: dict[str, Any] | None = None
        async with self._create_client(raw_connection=True) as hyperion_client:
            if hyperion_client:
                # The Hyperion-py client has a default timeout of 3 minutes on this request.
                auth_resp = await hyperion_client.async_request_token(
                    comment=DEFAULT_ORIGIN, id=auth_id
                )
            await self.hass.config_entries.flow.async_configure(
                flow_id=self.flow_id, user_input=auth_resp
            )

    def _get_hyperion_url(self) -> str:
        """Return the URL of the Hyperion UI."""
        # If this flow was kicked off by SSDP, this will be the correct frontend URL. If
        # this is a manual flow instantiation, then it will be a best guess (as this
        # flow does not have that information available to it). This is only used for
        # approving new dynamically created tokens, so the complexity of asking the user
        # manually for this information is likely not worth it (when it would only be
        # used to open a URL, that the user already knows the address of).
        return f"http://{self._data[CONF_HOST]}:{self._port_ui}"

    async def _can_login(self) -> bool | None:
        """Verify login details."""
        async with self._create_client(raw_connection=True) as hyperion_client:
            if not hyperion_client:
                return None
            return bool(
                client.LoginResponseOK(
                    await hyperion_client.async_login(token=self._data[CONF_TOKEN])
                )
            )

    async def async_step_auth(
        self,
        user_input: ConfigType | None = None,
    ) -> FlowResult:
        """Handle the auth step of a flow."""
        errors = {}
        if user_input:
            if user_input.get(CONF_CREATE_TOKEN):
                return await self.async_step_create_token()

            # Using a static token.
            self._data[CONF_TOKEN] = user_input.get(CONF_TOKEN)
            login_ok = await self._can_login()
            if login_ok is None:
                return self.async_abort(reason="cannot_connect")
            if login_ok:
                return await self.async_step_confirm()
            errors[CONF_BASE] = "invalid_access_token"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CREATE_TOKEN): bool,
                    vol.Optional(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_create_token(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Send a request for a new token."""
        if user_input is None:
            self._auth_id = client.generate_random_auth_id()
            return self.async_show_form(
                step_id="create_token",
                description_placeholders={
                    CONF_AUTH_ID: self._auth_id,
                },
            )

        # Cancel the request token task if it's already running, then re-create it.
        await self._cancel_request_token_task()
        # Start a task in the background requesting a new token. The next step will
        # wait on the response (which includes the user needing to visit the Hyperion
        # UI to approve the request for a new token).
        assert self._auth_id is not None
        self._request_token_task = self.hass.async_create_task(
            self._request_token_task_func(self._auth_id)
        )
        return self.async_external_step(
            step_id="create_token_external", url=self._get_hyperion_url()
        )

    async def async_step_create_token_external(
        self, auth_resp: ConfigType | None = None
    ) -> FlowResult:
        """Handle completion of the request for a new token."""
        if auth_resp is not None and client.ResponseOK(auth_resp):
            token = auth_resp.get(const.KEY_INFO, {}).get(const.KEY_TOKEN)
            if token:
                self._data[CONF_TOKEN] = token
                return self.async_external_step_done(
                    next_step_id="create_token_success"
                )
        return self.async_external_step_done(next_step_id="create_token_fail")

    async def async_step_create_token_success(
        self, _: ConfigType | None = None
    ) -> FlowResult:
        """Create an entry after successful token creation."""
        # Clean-up the request task.
        await self._cancel_request_token_task()

        # Test the token.
        login_ok = await self._can_login()

        if login_ok is None:
            return self.async_abort(reason="cannot_connect")
        if not login_ok:
            return self.async_abort(reason="auth_new_token_not_work_error")
        return await self.async_step_confirm()

    async def async_step_create_token_fail(
        self, _: ConfigType | None = None
    ) -> FlowResult:
        """Show an error on the auth form."""
        # Clean-up the request task.
        await self._cancel_request_token_task()
        return self.async_abort(reason="auth_new_token_not_granted_error")

    async def async_step_confirm(
        self, user_input: ConfigType | None = None
    ) -> FlowResult:
        """Get final confirmation before entry creation."""
        if user_input is None and self._require_confirm:
            return self.async_show_form(
                step_id="confirm",
                description_placeholders={
                    CONF_HOST: self._data[CONF_HOST],
                    CONF_PORT: self._data[CONF_PORT],
                    CONF_ID: self.unique_id,
                },
            )

        async with self._create_client() as hyperion_client:
            if not hyperion_client:
                return self.async_abort(reason="cannot_connect")
            hyperion_id = await hyperion_client.async_sysinfo_id()

        if not hyperion_id:
            return self.async_abort(reason="no_id")

        entry = await self.async_set_unique_id(hyperion_id, raise_on_progress=False)

        if self.context.get(CONF_SOURCE) == SOURCE_REAUTH and entry is not None:
            self.hass.config_entries.async_update_entry(entry, data=self._data)
            # Need to manually reload, as the listener won't have been installed because
            # the initial load did not succeed (the reauth flow will not be initiated if
            # the load succeeds)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"{self._data[CONF_HOST]}:{self._data[CONF_PORT]}", data=self._data
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HyperionOptionsFlow:
        """Get the Hyperion Options flow."""
        return HyperionOptionsFlow(config_entry)


class HyperionOptionsFlow(OptionsFlow):
    """Hyperion options flow."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize a Hyperion options flow."""
        self._config_entry = config_entry

    def _create_client(self) -> client.HyperionClient:
        """Create and connect a client instance."""
        return create_hyperion_client(
            self._config_entry.data[CONF_HOST],
            self._config_entry.data[CONF_PORT],
            token=self._config_entry.data.get(CONF_TOKEN),
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        effects = {source: source for source in const.KEY_COMPONENTID_EXTERNAL_SOURCES}
        async with self._create_client() as hyperion_client:
            if not hyperion_client:
                return self.async_abort(reason="cannot_connect")
            for effect in hyperion_client.effects or []:
                if const.KEY_NAME in effect:
                    effects[effect[const.KEY_NAME]] = effect[const.KEY_NAME]

        # If a new effect is added to Hyperion, we always want it to show by default. So
        # rather than store a 'show list' in the config entry, we store a 'hide list'.
        # However, it's more intuitive to ask the user to select which effects to show,
        # so we inverse the meaning prior to storage.

        if user_input is not None:
            effect_show_list = user_input.pop(CONF_EFFECT_SHOW_LIST)
            user_input[CONF_EFFECT_HIDE_LIST] = sorted(
                set(effects) - set(effect_show_list)
            )
            return self.async_create_entry(title="", data=user_input)

        default_effect_show_list = list(
            set(effects)
            - set(self._config_entry.options.get(CONF_EFFECT_HIDE_LIST, []))
        )

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
                    vol.Optional(
                        CONF_EFFECT_SHOW_LIST,
                        default=default_effect_show_list,
                    ): cv.multi_select(effects),
                }
            ),
        )
