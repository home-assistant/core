"""Config flow to configure Nest."""
import asyncio
from collections import OrderedDict
import logging
import os

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import load_json

from .const import DOMAIN

DATA_FLOW_IMPL = "nest_flow_implementation"
_LOGGER = logging.getLogger(__name__)


@callback
def register_flow_implementation(hass, domain, name, gen_authorize_url, convert_code):
    """Register a flow implementation.

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


@config_entries.HANDLERS.register(DOMAIN)
class NestFlowHandler(config_entries.ConfigFlow):
    """Handle a Nest config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        """Initialize the Nest config flow."""
        self.flow_impl = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        flows = self.hass.data.get(DATA_FLOW_IMPL, {})

        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        if not flows:
            return self.async_abort(reason="no_flows")

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
                errors["code"] = "invalid_code"
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
            return self.async_abort(reason="authorize_url_fail")

        return self.async_show_form(
            step_id="link",
            description_placeholders={"url": url},
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
        )

    async def async_step_import(self, info):
        """Import existing auth from Nest."""
        if self.hass.config_entries.async_entries(DOMAIN):
            return self.async_abort(reason="already_setup")

        config_path = info["nest_conf_path"]

        if not await self.hass.async_add_job(os.path.isfile, config_path):
            self.flow_impl = DOMAIN
            return await self.async_step_link()

        flow = self.hass.data[DATA_FLOW_IMPL][DOMAIN]
        tokens = await self.hass.async_add_job(load_json, config_path)

        return self._entry_from_tokens(
            "Nest (import from configuration.yaml)", flow, tokens
        )

    @callback
    def _entry_from_tokens(self, title, flow, tokens):
        """Create an entry from tokens."""
        return self.async_create_entry(
            title=title, data={"tokens": tokens, "impl_domain": flow["domain"]}
        )
