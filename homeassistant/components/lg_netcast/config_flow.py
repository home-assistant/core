"""Config flow to configure the LG Netcast TV integration."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from pylgnetcast import AccessTokenError, LgNetCastClient, SessionIdError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.network import is_host_valid

from .const import DEFAULT_NAME, DOMAIN
from .helpers import LGNetCastDetailDiscoveryError, async_discover_netcast_details

DISPLAY_ACCESS_TOKEN_INTERVAL = timedelta(seconds=1)


class LGNetCast(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Netcast TV integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.client: LgNetCastClient | None = None
        self.device_config: dict[str, Any] = {}
        self._discovered_devices: dict[str, Any] = {}
        self._track_interval: CALLBACK_TYPE | None = None

    def create_client(self) -> None:
        """Create LG Netcast client from config."""
        host = self.device_config[CONF_HOST]
        access_token = self.device_config.get(CONF_ACCESS_TOKEN)
        self.client = LgNetCastClient(host, access_token)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if is_host_valid(host):
                self.device_config[CONF_HOST] = host
                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_discover_client(self):
        """Handle Discovery step."""
        self.create_client()

        if TYPE_CHECKING:
            assert self.client is not None

        if self.device_config.get(CONF_ID):
            return

        try:
            details = await async_discover_netcast_details(self.hass, self.client)
        except LGNetCastDetailDiscoveryError as err:
            raise AbortFlow("cannot_connect") from err

        if (unique_id := details["uuid"]) is None:
            raise AbortFlow("invalid_host")

        self.device_config[CONF_ID] = unique_id
        self.device_config[CONF_MODEL] = details["model_name"]

        if CONF_NAME not in self.device_config:
            self.device_config[CONF_NAME] = details["friendly_name"] or DEFAULT_NAME

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Authorize step."""
        errors: dict[str, str] = {}
        self.async_stop_display_access_token()

        if user_input is not None and user_input.get(CONF_ACCESS_TOKEN) is not None:
            self.device_config[CONF_ACCESS_TOKEN] = user_input[CONF_ACCESS_TOKEN]

        await self.async_discover_client()
        assert self.client is not None

        await self.async_set_unique_id(self.device_config[CONF_ID])
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.device_config[CONF_HOST]}
        )

        try:
            await self.hass.async_add_executor_job(
                self.client._get_session_id  # noqa: SLF001
            )
        except AccessTokenError:
            if user_input is not None:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
        except SessionIdError:
            errors["base"] = "cannot_connect"
        else:
            return await self.async_create_device()

        self._track_interval = async_track_time_interval(
            self.hass,
            self.async_display_access_token,
            DISPLAY_ACCESS_TOKEN_INTERVAL,
            cancel_on_shutdown=True,
        )

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ACCESS_TOKEN): vol.All(str, vol.Length(max=6)),
                }
            ),
            errors=errors,
        )

    async def async_display_access_token(self, _: datetime | None = None):
        """Display access token on screen."""
        assert self.client is not None
        with contextlib.suppress(AccessTokenError, SessionIdError):
            await self.hass.async_add_executor_job(
                self.client._get_session_id  # noqa: SLF001
            )

    @callback
    def async_remove(self):
        """Terminate Access token display if flow is removed."""
        self.async_stop_display_access_token()

    def async_stop_display_access_token(self):
        """Stop Access token request if running."""
        if self._track_interval is not None:
            self._track_interval()
            self._track_interval = None

    async def async_create_device(self) -> ConfigFlowResult:
        """Create LG Netcast TV Device from config."""
        assert self.client

        return self.async_create_entry(
            title=self.device_config[CONF_NAME], data=self.device_config
        )
