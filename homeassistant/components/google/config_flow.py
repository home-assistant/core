"""Config flow for Google integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from gcal_sync.api import GoogleCalendarService
from gcal_sync.exceptions import ApiException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DEVICE_AUTH_CREDS,
    AccessTokenAuthImpl,
    DeviceAuth,
    DeviceFlow,
    OAuthError,
    async_create_device_flow,
    get_feature_access,
)
from .const import CONF_CALENDAR_ACCESS, DOMAIN, FeatureAccess

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Calendars OAuth2 authentication."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Set up instance."""
        super().__init__()
        self._reauth_config_entry: config_entries.ConfigEntry | None = None
        self._device_flow: DeviceFlow | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_import(self, info: dict[str, Any]) -> FlowResult:
        """Import existing auth into a new config entry."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        implementations = await config_entry_oauth2_flow.async_get_implementations(
            self.hass, self.DOMAIN
        )
        assert len(implementations) == 1
        self.flow_impl = list(implementations.values())[0]
        self.external_data = info
        return await super().async_step_creation(info)

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Create an entry for auth."""
        # The default behavior from the parent class is to redirect the
        # user with an external step. When using the device flow, we instead
        # prompt the user to visit a URL and enter a code. The device flow
        # background task will poll the exchange endpoint to get valid
        # creds or until a timeout is complete.
        if user_input is not None:
            return self.async_show_progress_done(next_step_id="creation")

        if not self._device_flow:
            _LOGGER.debug("Creating DeviceAuth flow")
            if not isinstance(self.flow_impl, DeviceAuth):
                _LOGGER.error(
                    "Unexpected OAuth implementation does not support device auth: %s",
                    self.flow_impl,
                )
                return self.async_abort(reason="oauth_error")
            calendar_access = get_feature_access(self.hass)
            if self._reauth_config_entry and self._reauth_config_entry.options:
                calendar_access = FeatureAccess[
                    self._reauth_config_entry.options[CONF_CALENDAR_ACCESS]
                ]
            try:
                device_flow = await async_create_device_flow(
                    self.hass,
                    self.flow_impl.client_id,
                    self.flow_impl.client_secret,
                    calendar_access,
                )
            except TimeoutError as err:
                _LOGGER.error("Timeout initializing device flow: %s", str(err))
                return self.async_abort(reason="timeout_connect")
            except OAuthError as err:
                _LOGGER.error("Error initializing device flow: %s", str(err))
                return self.async_abort(reason="oauth_error")
            self._device_flow = device_flow

            def _exchange_finished() -> None:
                self.external_data = {
                    DEVICE_AUTH_CREDS: device_flow.creds
                }  # is None on timeout/expiration
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_configure(
                        flow_id=self.flow_id, user_input={}
                    )
                )

            device_flow.async_set_listener(_exchange_finished)
            device_flow.async_start_exchange()

        return self.async_show_progress(
            step_id="auth",
            description_placeholders={
                "url": self._device_flow.verification_url,
                "user_code": self._device_flow.user_code,
            },
            progress_action="exchange",
        )

    async def async_step_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle external yaml configuration."""
        if self.external_data.get(DEVICE_AUTH_CREDS) is None:
            return self.async_abort(reason="code_expired")
        return await super().async_step_creation(user_input)

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        if self._reauth_config_entry:
            self.hass.config_entries.async_update_entry(
                self._reauth_config_entry, data=data
            )
            await self.hass.config_entries.async_reload(
                self._reauth_config_entry.entry_id
            )
            return self.async_abort(reason="reauth_successful")
        calendar_service = GoogleCalendarService(
            AccessTokenAuthImpl(
                async_get_clientsession(self.hass), data["token"]["access_token"]
            )
        )
        try:
            primary_calendar = await calendar_service.async_get_calendar("primary")
        except ApiException as err:
            _LOGGER.error("Error reading primary calendar: %s", err)
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(primary_calendar.id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=primary_calendar.id,
            data=data,
            options={
                CONF_CALENDAR_ACCESS: get_feature_access(self.hass).name,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create an options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Google Calendar options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CALENDAR_ACCESS,
                        default=self.config_entry.options.get(CONF_CALENDAR_ACCESS),
                    ): vol.In(
                        {
                            "read_write": "Read/Write access (can create events)",
                            "read_only": "Read-only access",
                        }
                    )
                }
            ),
        )
