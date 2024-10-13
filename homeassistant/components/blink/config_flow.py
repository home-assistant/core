"""Config flow to configure Blink."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from blinkpy.auth import Auth, LoginError, TokenRefreshFailed
from blinkpy.blinkpy import Blink, BlinkSetupError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(auth: Auth) -> None:
    """Validate the user input allows us to connect."""
    try:
        await auth.startup()
    except (LoginError, TokenRefreshFailed) as err:
        raise InvalidAuth from err
    if auth.check_key_required():
        raise Require2FA


async def _send_blink_2fa_pin(hass: HomeAssistant, auth: Auth, pin: str | None) -> bool:
    """Send 2FA pin to blink servers."""
    blink = Blink(session=async_get_clientsession(hass))
    blink.auth = auth
    blink.setup_login_ids()
    blink.setup_urls()
    return await auth.send_auth_key(blink, pin)


class BlinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the blink flow."""
        self.auth: Auth | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            self.auth = Auth(
                {**user_input, "device_id": DEVICE_ID},
                no_prompt=True,
                session=async_get_clientsession(self.hass),
            )
            await self.async_set_unique_id(user_input[CONF_USERNAME])

            try:
                await validate_input(self.auth)
                return self._async_finish_flow()
            except Require2FA:
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle 2FA step."""
        errors = {}
        if user_input is not None:
            try:
                valid_token = await _send_blink_2fa_pin(
                    self.hass, self.auth, user_input.get(CONF_PIN)
                )
            except BlinkSetupError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            else:
                if valid_token:
                    return self._async_finish_flow()
                errors["base"] = "invalid_access_token"

        return self.async_show_form(
            step_id="2fa",
            data_schema=vol.Schema(
                {vol.Optional(CONF_PIN): vol.All(str, vol.Length(min=1))}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon migration of old entries."""
        return await self.async_step_user(dict(entry_data))

    @callback
    def _async_finish_flow(self) -> ConfigFlowResult:
        """Finish with setup."""
        assert self.auth
        return self.async_create_entry(title=DOMAIN, data=self.auth.login_attributes)


class Require2FA(HomeAssistantError):
    """Error to indicate we require 2FA."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
