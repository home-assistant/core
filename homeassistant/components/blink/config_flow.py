"""Config flow to configure Blink."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from blinkpy.auth import Auth, LoginError, TokenRefreshFailed
from blinkpy.blinkpy import Blink, BlinkSetupError
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import DEFAULT_SCAN_INTERVAL, DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

SIMPLE_OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


def _get_blink_from_handler(handler: SchemaOptionsFlowHandler) -> Blink:
    """Extract blink instance from hass.data."""
    entry_id = handler.config_entry.entry_id
    blink: Blink = handler.hass.data[DOMAIN][entry_id]
    return blink


def _get_options_init_schema(handler: SchemaCommonFlowHandler) -> None:
    """Initialise handler, and return `None` to jump to next step."""
    parent_handler = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    blink = _get_blink_from_handler(parent_handler)
    parent_handler.options[CONF_SCAN_INTERVAL] = blink.refresh_rate


def _validate_simple_options(
    handler: SchemaCommonFlowHandler, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Update refresh rate on blink instance."""
    parent_handler = cast(SchemaOptionsFlowHandler, handler.parent_handler)
    blink = _get_blink_from_handler(parent_handler)
    blink.refresh_rate = user_input[CONF_SCAN_INTERVAL]
    return user_input


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        _get_options_init_schema,
        next_step="simple_options",
    ),
    "simple_options": SchemaFlowFormStep(
        SIMPLE_OPTIONS_SCHEMA,
        validate_user_input=_validate_simple_options,
    ),
}


def validate_input(hass: core.HomeAssistant, auth):
    """Validate the user input allows us to connect."""
    try:
        auth.startup()
    except (LoginError, TokenRefreshFailed) as err:
        raise InvalidAuth from err
    if auth.check_key_required():
        raise Require2FA


def _send_blink_2fa_pin(auth, pin):
    """Send 2FA pin to blink servers."""
    blink = Blink()
    blink.auth = auth
    blink.setup_login_ids()
    blink.setup_urls()
    return auth.send_auth_key(blink, pin)


class BlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 3

    def __init__(self):
        """Initialize the blink flow."""
        self.auth = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SchemaOptionsFlowHandler:
        """Get options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        data = {CONF_USERNAME: "", CONF_PASSWORD: "", "device_id": DEVICE_ID}
        if user_input is not None:
            data[CONF_USERNAME] = user_input["username"]
            data[CONF_PASSWORD] = user_input["password"]

            self.auth = Auth(data, no_prompt=True)
            await self.async_set_unique_id(data[CONF_USERNAME])

            try:
                await self.hass.async_add_executor_job(
                    validate_input, self.hass, self.auth
                )
                return self._async_finish_flow()
            except Require2FA:
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = {
            vol.Required("username"): str,
            vol.Required("password"): str,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def async_step_2fa(self, user_input=None):
        """Handle 2FA step."""
        errors = {}
        if user_input is not None:
            pin = user_input.get(CONF_PIN)
            try:
                valid_token = await self.hass.async_add_executor_job(
                    _send_blink_2fa_pin, self.auth, pin
                )
            except BlinkSetupError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                if valid_token:
                    return self._async_finish_flow()
                errors["base"] = "invalid_access_token"

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema(
                {vol.Optional("pin"): vol.All(str, vol.Length(min=1))}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_user(dict(entry_data))

    @callback
    def _async_finish_flow(self):
        """Finish with setup."""
        return self.async_create_entry(title=DOMAIN, data=self.auth.login_attributes)


class Require2FA(exceptions.HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
