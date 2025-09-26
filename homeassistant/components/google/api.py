"""Client library for talking to Google APIs."""

from __future__ import annotations

import datetime
import logging
from typing import Any, cast

import aiohttp
from gcal_sync.auth import AbstractAuth
from oauth2client.client import (
    Credentials,
    DeviceFlowInfo,
    FlowExchangeError,
    OAuth2DeviceCodeError,
    OAuth2WebServerFlow,
)

from homeassistant.components.application_credentials import AuthImplementation
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import CONF_CALENDAR_ACCESS, DEFAULT_FEATURE_ACCESS, FeatureAccess
from .store import GoogleConfigEntry

_LOGGER = logging.getLogger(__name__)

EVENT_PAGE_SIZE = 100
EXCHANGE_TIMEOUT_SECONDS = 60
DEVICE_AUTH_CREDS = "creds"


class OAuthError(Exception):
    """OAuth related error."""


class InvalidCredential(OAuthError):
    """Error with an invalid credential that does not support device auth."""


class GoogleHybridAuth(AuthImplementation):
    """OAuth implementation that supports both Web Auth (base class) and Device Auth."""

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve a Google API Credentials object to Home Assistant token."""
        if DEVICE_AUTH_CREDS not in external_data:
            # Assume the Web Auth flow was used, so use the default behavior
            return await super().async_resolve_external_data(external_data)
        creds: Credentials = external_data[DEVICE_AUTH_CREDS]
        delta = creds.token_expiry.replace(tzinfo=datetime.UTC) - dt_util.utcnow()
        _LOGGER.debug(
            "Token expires at %s (in %s)", creds.token_expiry, delta.total_seconds()
        )
        return {
            "access_token": creds.access_token,
            "refresh_token": creds.refresh_token,
            "scope": " ".join(creds.scopes),
            "token_type": "Bearer",
            "expires_in": delta.total_seconds(),
        }


class DeviceFlow:
    """OAuth2 device flow for exchanging a code for an access token."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_flow: OAuth2WebServerFlow,
        device_flow_info: DeviceFlowInfo,
    ) -> None:
        """Initialize DeviceFlow."""
        self._hass = hass
        self._oauth_flow = oauth_flow
        self._device_flow_info: DeviceFlowInfo = device_flow_info
        self._exchange_task_unsub: CALLBACK_TYPE | None = None
        self._timeout_unsub: CALLBACK_TYPE | None = None
        self._listener: CALLBACK_TYPE | None = None
        self._creds: Credentials | None = None

    @property
    def verification_url(self) -> str:
        """Return the verification url that the user should visit to enter the code."""
        return self._device_flow_info.verification_url  # type: ignore[no-any-return]

    @property
    def user_code(self) -> str:
        """Return the code that the user should enter at the verification url."""
        return self._device_flow_info.user_code  # type: ignore[no-any-return]

    @callback
    def async_set_listener(
        self,
        update_callback: CALLBACK_TYPE,
    ) -> None:
        """Invoke the update callback when the exchange finishes or on timeout."""
        self._listener = update_callback

    @property
    def creds(self) -> Credentials | None:
        """Return result of exchange step or None on timeout."""
        return self._creds

    def async_start_exchange(self) -> None:
        """Start the device auth exchange flow polling."""
        _LOGGER.debug("Starting exchange flow")
        max_timeout = dt_util.utcnow() + datetime.timedelta(
            seconds=EXCHANGE_TIMEOUT_SECONDS
        )
        # For some reason, oauth.step1_get_device_and_user_codes() returns a datetime
        # object without tzinfo. For the comparison below to work, it needs one.
        user_code_expiry = self._device_flow_info.user_code_expiry.replace(
            tzinfo=datetime.UTC
        )
        expiration_time = min(user_code_expiry, max_timeout)

        self._exchange_task_unsub = async_track_time_interval(
            self._hass,
            self._async_poll_attempt,
            datetime.timedelta(seconds=self._device_flow_info.interval),
        )
        self._timeout_unsub = async_track_point_in_utc_time(
            self._hass, self._async_timeout, expiration_time
        )

    async def _async_poll_attempt(self, now: datetime.datetime) -> None:
        _LOGGER.debug("Attempting OAuth code exchange")
        try:
            self._creds = await self._hass.async_add_executor_job(self._exchange)
        except FlowExchangeError:
            _LOGGER.debug("Token not yet ready; trying again later")
            return
        self._finish()

    def _exchange(self) -> Credentials:
        return self._oauth_flow.step2_exchange(device_flow_info=self._device_flow_info)

    @callback
    def _async_timeout(self, now: datetime.datetime) -> None:
        _LOGGER.debug("OAuth token exchange timeout")
        self._finish()

    @callback
    def _finish(self) -> None:
        if self._exchange_task_unsub:
            self._exchange_task_unsub()
        if self._timeout_unsub:
            self._timeout_unsub()
        if self._listener:
            self._listener()


def get_feature_access(config_entry: GoogleConfigEntry) -> FeatureAccess:
    """Return the desired calendar feature access."""
    if config_entry.options and CONF_CALENDAR_ACCESS in config_entry.options:
        return FeatureAccess[config_entry.options[CONF_CALENDAR_ACCESS]]
    return DEFAULT_FEATURE_ACCESS


async def async_create_device_flow(
    hass: HomeAssistant, client_id: str, client_secret: str, access: FeatureAccess
) -> DeviceFlow:
    """Create a new Device flow."""
    oauth_flow = OAuth2WebServerFlow(
        client_id=client_id,
        client_secret=client_secret,
        scope=access.scope,
        redirect_uri="",
    )
    try:
        device_flow_info = await hass.async_add_executor_job(
            oauth_flow.step1_get_device_and_user_codes
        )
    except OAuth2DeviceCodeError as err:
        _LOGGER.debug("OAuth2DeviceCodeError error: %s", err)
        # Web auth credentials reply with invalid_client when hitting this endpoint
        if "Error: invalid_client" in str(err):
            raise InvalidCredential(str(err)) from err
        raise OAuthError(str(err)) from err
    return DeviceFlow(hass, oauth_flow, device_flow_info)


class ApiAuthImpl(AbstractAuth):
    """Authentication implementation for google calendar api library."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Init the Google Calendar client library auth implementation."""
        super().__init__(websession)
        self._session = session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        await self._session.async_ensure_token_valid()
        return cast(str, self._session.token["access_token"])


class AccessTokenAuthImpl(AbstractAuth):
    """Authentication implementation used during config flow, without refresh.

    This exists to allow the config flow to use the API before it has fully
    created a config entry required by OAuth2Session. This does not support
    refreshing tokens, which is fine since it should have been just created.
    """

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        access_token: str,
    ) -> None:
        """Init the Google Calendar client library auth implementation."""
        super().__init__(websession)
        self._access_token = access_token

    async def async_get_access_token(self) -> str:
        """Return the access token."""
        return self._access_token
