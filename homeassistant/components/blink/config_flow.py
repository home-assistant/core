"""Config flow to configure Blink."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from blinkpy.auth import Auth, BlinkTwoFARequiredError, LoginError, TokenRefreshFailed
from blinkpy.blinkpy import Blink, BlinkSetupError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEVICE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(blink: Blink) -> None:
    """Validate the user input allows us to connect."""
    try:
        await blink.start()
    except (LoginError, TokenRefreshFailed) as err:
        raise InvalidAuth from err


async def _send_blink_2fa_pin(blink: Blink, pin: str | None) -> bool:
    """Send 2FA pin to blink servers."""
    await blink.send_2fa_code(pin)
    return True


class BlinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Blink config flow."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the blink flow."""
        self.auth: Auth | None = None
        self.blink: Blink | None = None

    async def _handle_user_input(self, user_input: dict[str, Any]):
        """Handle user input."""
        self.auth = Auth(
            {**user_input, "device_id": DEVICE_ID},
            no_prompt=True,
            session=async_get_clientsession(self.hass),
        )
        self.blink = Blink(session=async_get_clientsession(self.hass))
        self.blink.auth = self.auth
        await self.async_set_unique_id(user_input[CONF_USERNAME])
        if self.source not in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            self._abort_if_unique_id_configured()

        await validate_input(self.blink)
        return self._async_finish_flow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            try:
                return await self._handle_user_input(user_input)
            except BlinkTwoFARequiredError:
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
                await _send_blink_2fa_pin(self.blink, user_input.get(CONF_PIN))
                return self._async_finish_flow()
            except BlinkSetupError:
                errors["base"] = "cannot_connect"
            except TokenRefreshFailed:
                errors["base"] = "invalid_access_token"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

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
        """Perform reauth after an authentication error."""
        return await self.async_step_reauth_confirm(None)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors = {}
        if user_input is not None:
            try:
                return await self._handle_user_input(user_input)
            except BlinkTwoFARequiredError:
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        config_entry = self._get_reauth_entry()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=config_entry.data[CONF_USERNAME]
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=config_entry.data[CONF_PASSWORD]
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders={"username": config_entry.data[CONF_USERNAME]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration initiated by the user."""
        errors = {}
        if user_input is not None:
            try:
                return await self._handle_user_input(user_input)
            except BlinkTwoFARequiredError:
                return await self.async_step_2fa()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        config_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=config_entry.data[CONF_USERNAME]
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=config_entry.data[CONF_PASSWORD]
                    ): str,
                }
            ),
            errors=errors,
        )

    @callback
    def _async_finish_flow(self) -> ConfigFlowResult:
        """Finish with setup."""
        assert self.auth

        if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
            return self.async_update_reload_and_abort(
                self._get_reauth_entry()
                if self.source == SOURCE_REAUTH
                else self._get_reconfigure_entry(),
                data_updates=self.auth.login_attributes,
            )

        return self.async_create_entry(title=DOMAIN, data=self.auth.login_attributes)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
