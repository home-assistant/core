"""Config flow to configure Nest.

This configuration flow supports two APIs:
  - The new Device Access program and the Smart Device Management API
  - The legacy nest API

NestFlowHandler is an implementation of AbstractOAuth2FlowHandler with
some overrides to support the old APIs auth flow.  That is, for the new
API this class has hardly any special config other than url parameters,
and everything else custom is for the old api.  When configured with the
new api via NestFlowHandler.register_sdm_api, the custom methods just
invoke the AbstractOAuth2FlowHandler methods.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import logging
import os

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.json import load_json

from .const import DATA_SDM, DOMAIN, SDM_SCOPES

DATA_FLOW_IMPL = "nest_flow_implementation"
_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, domain, name, gen_authorize_url, convert_code):
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


class NestFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle authentication for both APIs."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self):
        """Initialize NestFlowHandler."""
        super().__init__()
        # When invoked for reauth, allows updating an existing config entry
        self._reauth = False

    @classmethod
    def register_sdm_api(cls, hass):
        """Configure the flow handler to use the SDM API."""
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        hass.data[DOMAIN][DATA_SDM] = {}

    def is_sdm_api(self):
        """Return true if this flow is setup to use SDM API."""
        return DOMAIN in self.hass.data and DATA_SDM in self.hass.data[DOMAIN]

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SDM_SCOPES),
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the SDM flow."""
        assert self.is_sdm_api(), "Step only supported for SDM API"
        data[DATA_SDM] = {}
        await self.async_set_unique_id(DOMAIN)
        # Update existing config entry when in the reauth flow.  This
        # integration only supports one config entry so remove any prior entries
        # added before the "single_instance_allowed" check was added
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)
        if existing_entries:
            updated = False
            for entry in existing_entries:
                if updated:
                    await self.hass.config_entries.async_remove(entry.entry_id)
                    continue
                updated = True
                self.hass.config_entries.async_update_entry(
                    entry, data=data, unique_id=DOMAIN
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return await super().async_oauth_create_entry(data)

    async def async_step_reauth(self, user_input=None):
        """Perform reauth upon an API authentication error."""
        assert self.is_sdm_api(), "Step only supported for SDM API"
        self._reauth = True  # Forces update of existing config entry
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Confirm reauth dialog."""
        assert self.is_sdm_api(), "Step only supported for SDM API"
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self.is_sdm_api():
            # Reauth will update an existing entry
            if self.hass.config_entries.async_entries(DOMAIN) and not self._reauth:
                return self.async_abort(reason="single_instance_allowed")
            return await super().async_step_user(user_input)
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        assert not self.is_sdm_api(), "Step only supported for legacy API"

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
