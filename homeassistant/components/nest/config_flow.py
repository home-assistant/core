"""Config flow to configure Nest.

This configuration flow supports two APIs:
  - The new Device Access program and the Smart Device Management (SDM) API
  - The Legacy Works with Nest API

The SDM API can be configured entirely via this config flow, but also supports
backwards compatibility with the old approach of using configuration.yaml.
An integration has a single class for config flows, so this one flow file
supports all variations of config flows.  The legacy API config flow is enabled
via register_flow_implementation.

This config flow inherits from AbstractOAuth2FlowHandler to handle most of the
OAuth functionality, redirects, and token management.  The OAuth redirects
happen in the middle of the flow at the user needs to first provide some
configuration options.  This flow also supports a reauth step that handles
re-running the flow to update existing authentication tokens.

The notable config flow steps are:
- user: To dispatch between API versions and OAuth once configured.
- device_access: Prompt the user for parameters required to talk to the SDM API
- user: Invoked again, this time to run the OAuth flow in the parent class.
- async_oauth_create_entry: Overridden to handle when OAuth is complete.  This
    does not actually create the entry, but holds on to the OAuth token data
    for later
- pubsub: Configure the pubsub subscriber
- finish: Handles creating a new configuration entry or updating the existing
    configuration entry.

Any existing values from the deprecated use of configuration.yaml are used to
populate the default values in the config flow.
"""

import asyncio
from collections import OrderedDict
import logging
import os
from typing import Dict

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.json import load_json

from .const import (
    CONF_PROJECT_ID,
    CONF_SUBSCRIBER_ID,
    DATA_NEST_CONFIG,
    DATA_SDM,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SDM_SCOPES,
)

DATA_FLOW_IMPL = "nest_flow_implementation"
_LOGGER = logging.getLogger(__name__)


@callback
def register_legacy_flow_implementation(
    hass, domain, name, gen_authorize_url, convert_code
):
    """Register a flow implementation for legacy api.

    domain: Domain of the component responsible for the implementation.
    name: Name of the component.
    gen_authorize_url: Coroutine function to generate the authorize url.
    convert_code: Coroutine function to convert a code to an access token.
    """
    if DATA_FLOW_IMPL not in hass.data:
        hass.data[DATA_FLOW_IMPL] = OrderedDict()

    hass.data[DATA_FLOW_IMPL][domain] = {
        "domain": domain,
        "name": name,
        "gen_authorize_url": gen_authorize_url,
        "convert_code": convert_code,
    }


class NestAuthError(HomeAssistantError):
    """Base class for Nest auth errors."""


class CodeInvalid(NestAuthError):
    """Raised when invalid authorization code."""


class UnexpectedStateError(HomeAssistantError):
    """Raised when the config flow is invoked in a 'should not happen' case."""


@config_entries.HANDLERS.register(DOMAIN)
class NestFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle authentication for both APIs."""

    DOMAIN = DOMAIN
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize NestFlowHandler."""
        super().__init__()
        # Allows updating an existing config entry
        self._reauth_data = None
        # ConfigEntry data for SDM API
        self._data = {DATA_SDM: {}}

    def is_sdm_api(self):
        """Return true if this flow is setup to use SDM API."""
        # Legacy flow always calls register_flow_implementation above
        return DATA_FLOW_IMPL not in self.hass.data

    @classmethod
    def async_register_oauth(cls, hass, client_id, client_secret, project_id):
        """Register and return the singleton oauth implementation."""
        # Note: Only one configuration is allowed, so this is safe to always
        # overwrite the existing implementation if config changes.
        implementation = config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            client_id,
            client_secret,
            OAUTH2_AUTHORIZE.format(project_id=project_id),
            OAUTH2_TOKEN,
        )
        NestFlowHandler.async_register_implementation(hass, implementation)
        return implementation

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> Dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SDM_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    @property
    def _defaults(self) -> dict:
        """Return default values from existing entry or configuration.yaml."""
        if self._reauth_data and CONF_PROJECT_ID in self._reauth_data:
            return self._reauth_data
        return self.hass.data.get(DOMAIN, {}).get(DATA_NEST_CONFIG, {})

    async def _cleanup_invalid_config_entries(self):
        """Update or remove non-conforming config entries."""
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        if existing_entries:
            # Add a unique_id if not present on existing config entry
            first_entry = existing_entries[0]
            if first_entry.unique_id != DOMAIN:
                self.hass.config_entries.async_update_entry(
                    first_entry, data=first_entry.data, unique_id=DOMAIN
                )
            # Remove entries added before the "single_instance_allowed" check
            # was implemented in the config flow
            for entry in existing_entries[1:]:
                await self.hass.config_entries.async_remove(entry.entry_id)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user, and dispatch between APIs."""
        if not self.is_sdm_api():
            return await self.async_step_init(user_input)
        # This method async_step_user overrides the first step of the OAuth
        # flow to insert a step (async_step_device_access) to prompt for
        # necessary OAuth related configuration options.  The parent class
        # async_step_user is then invoked to actually initiate the OAuth flow.
        await self._cleanup_invalid_config_entries()
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry and not self._reauth_data:
            return self.async_abort(reason="single_instance_allowed")
        return await self.async_step_device_access()

    async def async_step_device_access(self, user_input=None):
        """Enter configuration options for the Device Access project."""
        if user_input is None:
            data_schema = {
                vol.Required(
                    CONF_PROJECT_ID, default=self._defaults.get(CONF_PROJECT_ID)
                ): str,
                vol.Required(
                    CONF_CLIENT_ID, default=self._defaults.get(CONF_CLIENT_ID)
                ): str,
                vol.Required(
                    CONF_CLIENT_SECRET, default=self._defaults.get(CONF_CLIENT_SECRET)
                ): str,
            }
            return self.async_show_form(
                step_id="device_access", data_schema=vol.Schema(data_schema)
            )
        self._data.update(user_input)
        # Configure OAuth and invoke parent async_step_user to initiate flow
        NestFlowHandler.async_register_oauth(
            self.hass,
            user_input[CONF_CLIENT_ID],
            user_input[CONF_CLIENT_SECRET],
            user_input[CONF_PROJECT_ID],
        )
        return await super().async_step_user()

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Initiate subscriber setup after OAuth redirects are complete."""
        # OAuth tokens are persisted in the final step async_step-finish
        self._data.update(data)
        return await self.async_step_pubsub()

    async def async_step_pubsub(self, user_input: dict = None) -> dict:
        """Configure Pub/Sub subscriber."""
        if user_input is None:
            data_schema = {
                vol.Required(
                    CONF_SUBSCRIBER_ID, default=self._defaults.get(CONF_SUBSCRIBER_ID)
                ): str,
            }
            return self.async_show_form(
                step_id="pubsub", data_schema=vol.Schema(data_schema)
            )
        self._data.update(user_input)
        return await self.async_step_finish()

    async def async_step_finish(self, data=None):
        """Create the Nest SDM API ConfigEntry."""
        # Replace any existing entries when in the reauth flow.
        existing_entry = await self.async_set_unique_id(DOMAIN)
        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=self._data, unique_id=DOMAIN
            )
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await super().async_oauth_create_entry(self._data)

    async def async_step_reauth(self, data=None):
        """Perform reauth upon an API authentication error."""
        if data is None:
            _LOGGER.error("Reauth invoked with empty config entry data.")
            return self.async_abort(reason="missing_configuration")
        self._reauth_data = data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_step_init(self, user_input=None):
        """Handle Legacy work with Nest API flow start."""
        if self.is_sdm_api():
            _LOGGER.error("async_step_init only supported for legacy API")
            return self.async_abort(reason="missing_configuration")

        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        if not flows:
            return self.async_abort(reason="missing_configuration")

        if len(flows) == 1:
            self.flow_impl = list(flows)[0]
            return await self.async_step_link()

        if user_input is not None:
            self.flow_impl = user_input["flow_impl"]
            return await self.async_step_link()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("flow_impl"): vol.In(list(flows))}),
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Nest account.

        Route the user to a website to authenticate with Nest. Depending on
        implementation type we expect a pin or an external component to
        deliver the authentication code.
        """
        assert not self.is_sdm_api(), "Step only supported for legacy API"

        flow = self.hass.data[DATA_FLOW_IMPL][self.flow_impl]

        errors = {}

        if user_input is not None:
            try:
                with async_timeout.timeout(10):
                    tokens = await flow["convert_code"](user_input["code"])
                return self._entry_from_tokens(
                    f"Nest (via {flow['name']})", flow, tokens
                )

            except asyncio.TimeoutError:
                errors["code"] = "timeout"
            except CodeInvalid:
                errors["code"] = "invalid_pin"
            except NestAuthError:
                errors["code"] = "unknown"
            except Exception:  # pylint: disable=broad-except
                errors["code"] = "internal_error"
                _LOGGER.exception("Unexpected error resolving code")

        try:
            with async_timeout.timeout(10):
                url = await flow["gen_authorize_url"](self.flow_id)
        except asyncio.TimeoutError:
            return self.async_abort(reason="authorize_url_timeout")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error generating auth url")
            return self.async_abort(reason="unknown_authorize_url_generation")

        return self.async_show_form(
            step_id="link",
            description_placeholders={"url": url},
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
        )

    async def async_step_import(self, info):
        """Import existing auth from Nest."""
        assert not self.is_sdm_api(), "Step only supported for legacy API"

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="single_instance_allowed")

        config_path = info["nest_conf_path"]

        if not await self.hass.async_add_executor_job(os.path.isfile, config_path):
            self.flow_impl = DOMAIN
            return await self.async_step_link()

        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        tokens = await self.hass.async_add_executor_job(load_json, config_path)

        return self._entry_from_tokens(
            "Nest (import from configuration.yaml)", flow, tokens
        )

    @callback
    def _entry_from_tokens(self, title, flow, tokens):
        """Create an entry from tokens."""
        return self.async_create_entry(
            title=title, data={"tokens": tokens, "impl_domain": flow["domain"]}
        )
