"""Config flow to configure the Pi-hole integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from hole.exceptions import HoleError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_LOCATION,
    CONF_NAME,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)

from . import Hole, api_by_version, determine_api_version
from .const import (
    DEFAULT_LOCATION,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PiHoleFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pi-hole config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._config = {
                CONF_HOST: f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                CONF_NAME: user_input[CONF_NAME],
                CONF_LOCATION: user_input[CONF_LOCATION],
                CONF_SSL: user_input[CONF_SSL],
                CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                CONF_API_KEY: user_input[CONF_API_KEY],
            }

            self._async_abort_entries_match(
                {
                    CONF_HOST: f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}",
                    CONF_LOCATION: user_input[CONF_LOCATION],
                }
            )

            if not (errors := await self._async_try_connect()):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=self._config
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST, "")): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, 80)
                    ): vol.Coerce(int),
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
                    vol.Required(
                        CONF_LOCATION,
                        default=user_input.get(CONF_LOCATION, DEFAULT_LOCATION),
                    ): str,
                    vol.Required(
                        CONF_API_KEY,
                        default=user_input.get(CONF_API_KEY),
                    ): str,
                    vol.Required(
                        CONF_SSL,
                        default=user_input.get(CONF_SSL, DEFAULT_SSL),
                    ): bool,
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self._config = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Perform reauth confirm upon an API authentication error."""
        errors = {}
        if user_input is not None:
            self._config = {**self._config, CONF_API_KEY: user_input[CONF_API_KEY]}
            if not (errors := await self._async_try_connect()):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data=self._config
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                CONF_HOST: self._config[CONF_HOST],
                CONF_LOCATION: self._config[CONF_LOCATION],
            },
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def _async_try_connect(self) -> dict[str, str]:
        """Try to connect to the Pi-hole API and determine the version."""
        try:
            version = await determine_api_version(hass=self.hass, entry=self._config)
        except HoleError:
            return {"base": "cannot_connect"}
        pi_hole: Hole = api_by_version(self.hass, self._config, version)

        if version == 6:
            try:
                await pi_hole.authenticate()
                _LOGGER.debug("Success authenticating with pihole API version: %s", 6)
            except HoleError:
                _LOGGER.debug("Failed authenticating with pihole API version: %s", 6)
                return {CONF_API_KEY: "invalid_auth"}

        elif version == 5:
            try:
                await pi_hole.get_data()
                if pi_hole.data is not None and "error" in pi_hole.data:
                    _LOGGER.debug(
                        "API version %s returned an unexpected error: %s",
                        5,
                        str(pi_hole.data),
                    )
                    raise HoleError(pi_hole.data)  # noqa: TRY301
            except HoleError as ex_v5:
                _LOGGER.error(
                    "Connection to API version 5 failed: %s",
                    ex_v5,
                )
                return {"base": "cannot_connect"}
            else:
                _LOGGER.debug(
                    "Success connecting to, but necessarily authenticating with, pihole, API version is: %s",
                    5,
                )
            # the v5 API returns an empty list to unauthenticated requests.
            if not isinstance(pi_hole.data, dict):
                _LOGGER.debug(
                    "API version %s returned %s, '[]' is expected for unauthenticated requests",
                    5,
                    pi_hole.data,
                )
                return {CONF_API_KEY: "invalid_auth"}
        return {}
