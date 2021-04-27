"""Config flow to configure Vorwerk integration."""
from __future__ import annotations

import logging
from typing import Any

import pybotvac
from pybotvac.exceptions import NeatoException
from requests.models import HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_TOKEN

from homeassistant.data_entry_flow import FlowResult

# pylint: disable=unused-import
from .const import (
    VORWERK_CLIENT_ID,
    VORWERK_DOMAIN,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)


class VorwerkConfigFlow(config_entries.ConfigFlow, domain=VORWERK_DOMAIN):
    """Vorwerk integration config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._email: str | None = None
        self._session = VorwerkSession()

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""

        if user_input is not None:
            self._email = user_input.get(CONF_EMAIL)
            if self._email:
                await self.async_set_unique_id(self._email)
                self._abort_if_unique_id_configured()
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                }
            ),
        )

    async def async_step_code(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Step when user enters OTP Code from email."""
        assert self._email is not None  # typing
        errors = {}
        code = user_input.get(CONF_CODE) if user_input else None
        if code:
            try:
                robots = await self.hass.async_add_executor_job(
                    self._get_robots, self._email, code
                )
                return self.async_create_entry(
                    title=self._email,
                    data={
                        CONF_EMAIL: self._email,
                        CONF_TOKEN: self._session.token,
                        VORWERK_ROBOTS: robots,
                    },
                )
            except (HTTPError, NeatoException):
                errors["base"] = "invalid_auth"

        await self.hass.async_add_executor_job(
            self._session.send_email_otp, self._email
        )

        return self.async_show_form(
            step_id="code",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CODE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import a config flow from configuration."""
        unique_id = "from configuration"
        data = {VORWERK_ROBOTS: user_input}

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(data)

        _LOGGER.info("Creating new Vorwerk robot config entry")
        return self.async_create_entry(
            title="from configuration",
            data=data,
        )

    def _get_robots(self, email: str, code: str):
        """Fetch the robot list from vorwerk."""
        self._session.fetch_token_passwordless(email, code)
        return [
            {
                VORWERK_ROBOT_NAME: robot["name"],
                VORWERK_ROBOT_SERIAL: robot["serial"],
                VORWERK_ROBOT_SECRET: robot["secret_key"],
                VORWERK_ROBOT_TRAITS: robot["traits"],
                VORWERK_ROBOT_ENDPOINT: robot["nucleo_url"],
            }
            for robot in self._session.get("users/me/robots").json()
        ]


class VorwerkSession(pybotvac.PasswordlessSession):
    """PasswordlessSession pybotvac session for Vorwerk cloud."""

    def __init__(self):
        """Initialize Vorwerk cloud session."""
        super().__init__(client_id=VORWERK_CLIENT_ID, vendor=pybotvac.Vorwerk())

    @property
    def token(self):
        """Return the token dict. Contains id_token, access_token and refresh_token."""
        return self._token
