"""Config flow for Google integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from gcal_sync.api import GoogleCalendarService
from gcal_sync.exceptions import ApiException, ApiForbiddenException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DEVICE_AUTH_CREDS,
    AccessTokenAuthImpl,
    DeviceFlow,
    GoogleHybridAuth,
    InvalidCredential,
    OAuthError,
    async_create_device_flow,
    get_feature_access,
)
from .const import (
    CONF_CALENDAR_ACCESS,
    CONF_CREDENTIAL_TYPE,
    DEFAULT_FEATURE_ACCESS,
    DOMAIN,
    CredentialType,
    FeatureAccess,
)

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Google Calendars OAuth2 authentication.

    Historically, the Google Calendar integration instructed users to use
    Device Auth. Device Auth was considered easier to use since it did not
    require users to configure a redirect URL. Device Auth is meant for
    devices with limited input, such as a television.
    https://developers.google.com/identity/protocols/oauth2/limited-input-device

    Device Auth is limited to a small set of Google APIs (calendar is allowed)
    and is considered less secure than Web Auth. It is not generally preferred
    and may be limited/deprecated in the future similar to App/OOB Auth
    https://developers.googleblog.com/2022/02/making-oauth-flows-safer.html

    Web Auth is the preferred method by Home Assistant and Google, and a benefit
    is that the same credentials may be used across many Google integrations in
    Home Assistant. Web Auth is now easier for user to setup using my.home-assistant.io
    redirect urls.

    The Application Credentials integration does not currently record which type
    of credential the user entered (and if we ask the user, they may not know or may
    make a mistake) so we try to determine the credential type automatically. This
    implementation first attempts Device Auth by talking to the token API in the first
    step of the device flow, then if that fails it will redirect using Web Auth.
    There is not another explicit known way to check.
    """

    DOMAIN = DOMAIN

    _exchange_finished_task: asyncio.Task[bool] | None = None

    def __init__(self) -> None:
        """Set up instance."""
        super().__init__()
        self._reauth_config_entry: config_entries.ConfigEntry | None = None
        self._device_flow: DeviceFlow | None = None
        # First attempt is device auth, then fallback to web auth
        self._web_auth = False

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": DEFAULT_FEATURE_ACCESS.scope,
            # Add params to ensure we get back a refresh token
            "access_type": "offline",
            "prompt": "consent",
        }

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
        if self._web_auth:
            return await super().async_step_auth(user_input)

        if self._exchange_finished_task and self._exchange_finished_task.done():
            return self.async_show_progress_done(next_step_id="creation")

        if not self._device_flow:
            _LOGGER.debug("Creating GoogleHybridAuth flow")
            if not isinstance(self.flow_impl, GoogleHybridAuth):
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
            except InvalidCredential:
                _LOGGER.debug("Falling back to Web Auth and restarting flow")
                self._web_auth = True
                return await super().async_step_auth()
            except OAuthError as err:
                _LOGGER.error("Error initializing device flow: %s", str(err))
                return self.async_abort(reason="oauth_error")
            self._device_flow = device_flow

            exchange_finished_evt = asyncio.Event()
            self._exchange_finished_task = self.hass.async_create_task(
                exchange_finished_evt.wait()
            )

            def _exchange_finished() -> None:
                self.external_data = {
                    DEVICE_AUTH_CREDS: device_flow.creds
                }  # is None on timeout/expiration
                exchange_finished_evt.set()

            device_flow.async_set_listener(_exchange_finished)
            device_flow.async_start_exchange()

        return self.async_show_progress(
            step_id="auth",
            description_placeholders={
                "url": self._device_flow.verification_url,
                "user_code": self._device_flow.user_code,
            },
            progress_action="exchange",
            progress_task=self._exchange_finished_task,
        )

    async def async_step_creation(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle external yaml configuration."""
        if not self._web_auth and self.external_data.get(DEVICE_AUTH_CREDS) is None:
            return self.async_abort(reason="code_expired")
        return await super().async_step_creation(user_input)

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an entry for the flow, or update existing entry."""
        data[CONF_CREDENTIAL_TYPE] = (
            CredentialType.WEB_AUTH if self._web_auth else CredentialType.DEVICE_AUTH
        )
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
        except ApiForbiddenException as err:
            _LOGGER.error(
                "Error reading primary calendar, make sure Google Calendar API is enabled: %s",
                err,
            )
            return self.async_abort(reason="api_disabled")
        except ApiException as err:
            _LOGGER.error("Error reading primary calendar: %s", err)
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(primary_calendar.id)

        if found := self.hass.config_entries.async_entry_for_domain_unique_id(
            self.handler, primary_calendar.id
        ):
            _LOGGER.debug("Found existing '%s' entry: %s", primary_calendar.id, found)

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
        self._web_auth = entry_data.get(CONF_CREDENTIAL_TYPE) == CredentialType.WEB_AUTH
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
