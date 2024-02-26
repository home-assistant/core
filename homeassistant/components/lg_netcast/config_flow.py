"""Config flow to configure the LG Netcast TV integration."""
from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from pylgnetcast import AccessTokenError, LgNetCastClient, SessionIdError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import CALLBACK_TYPE, DOMAIN as HOMEASSISTANT_DOMAIN, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util.network import is_host_valid

from .const import (
    ATTR_FRIENDLY_NAME,
    ATTR_MODEL_NAME,
    ATTR_UUID,
    DEFAULT_NAME,
    DISPLAY_ACCESS_TOKEN_INTERVAL,
    DOMAIN,
)
from .helpers import LGNetCastDetailDiscoveryError, async_discover_netcast_details


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
    ) -> FlowResult:
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

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import configuration from yaml."""
        self.device_config = {
            CONF_HOST: config[CONF_HOST],
            CONF_NAME: config[CONF_NAME],
        }
        await self.async_discover_client()

        try:
            self._async_abort_entries_match({CONF_ID: self.device_config[CONF_ID]})
        except AbortFlow as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_already_configured",
                breaks_in_ha_version="2024.6.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_already_configured",
                translation_placeholders={
                    "domain": DOMAIN,
                    "interation_title": "LG Netcast",
                },
            )
            raise err

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "LG Netcast",
            },
        )

        return await self.async_step_authorize(config)

    async def async_discover_client(self):
        """Handle Discovery step."""
        self.create_client()
        assert self.client is not None

        if self.device_config.get(CONF_ID):
            return

        try:
            details = await async_discover_netcast_details(self.hass, self.client)
        except LGNetCastDetailDiscoveryError as err:
            raise AbortFlow("cannot_connect") from err

        if (unique_id := details[ATTR_UUID]) is None:
            raise AbortFlow("invalid_host")

        self.device_config[CONF_ID] = unique_id
        self.device_config[CONF_MODEL] = details[ATTR_MODEL_NAME]

        if CONF_NAME not in self.device_config:
            self.device_config[CONF_NAME] = details[ATTR_FRIENDLY_NAME] or DEFAULT_NAME

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
                self.client._get_session_id  # pylint: disable=protected-access
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

    @callback
    async def async_display_access_token(self, _: datetime | None = None):
        """Display access token on screen."""
        assert self.client is not None
        with contextlib.suppress(AccessTokenError, SessionIdError):
            await self.hass.async_add_executor_job(
                self.client._get_session_id  # pylint: disable=protected-access
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

    async def async_create_device(self) -> FlowResult:
        """Create LG Netcast TV Device from config."""
        assert self.client

        return self.async_create_entry(
            title=self.device_config[CONF_NAME], data=self.device_config
        )
