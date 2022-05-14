"""Client library for talking to Google APIs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
import logging
import time
from typing import Any

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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt

from .const import (
    CONF_CALENDAR_ACCESS,
    DATA_CONFIG,
    DEFAULT_FEATURE_ACCESS,
    DOMAIN,
    FeatureAccess,
)

_LOGGER = logging.getLogger(__name__)

EVENT_PAGE_SIZE = 100
EXCHANGE_TIMEOUT_SECONDS = 60
DEVICE_AUTH_CREDS = "creds"


class OAuthError(Exception):
    """OAuth related error."""


class DeviceAuth(AuthImplementation):
    """OAuth implementation for Device Auth."""

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve a Google API Credentials object to Home Assistant token."""
        creds: Credentials = external_data[DEVICE_AUTH_CREDS]
        return {
            "access_token": creds.access_token,
            "refresh_token": creds.refresh_token,
            "scope": " ".join(creds.scopes),
            "token_type": "Bearer",
            "expires_in": creds.token_expiry.timestamp() - time.time(),
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

    @property
    def verification_url(self) -> str:
        """Return the verification url that the user should visit to enter the code."""
        return self._device_flow_info.verification_url

    @property
    def user_code(self) -> str:
        """Return the code that the user should enter at the verification url."""
        return self._device_flow_info.user_code

    async def start_exchange_task(
        self, finished_cb: Callable[[Credentials | None], Awaitable[None]]
    ) -> None:
        """Start the device auth exchange flow polling.

        The callback is invoked with the valid credentials or with None on timeout.
        """
        _LOGGER.debug("Starting exchange flow")
        assert not self._exchange_task_unsub
        max_timeout = dt.utcnow() + datetime.timedelta(seconds=EXCHANGE_TIMEOUT_SECONDS)
        # For some reason, oauth.step1_get_device_and_user_codes() returns a datetime
        # object without tzinfo. For the comparison below to work, it needs one.
        user_code_expiry = self._device_flow_info.user_code_expiry.replace(
            tzinfo=datetime.timezone.utc
        )
        expiration_time = min(user_code_expiry, max_timeout)

        def _exchange() -> Credentials:
            return self._oauth_flow.step2_exchange(
                device_flow_info=self._device_flow_info
            )

        async def _poll_attempt(now: datetime.datetime) -> None:
            assert self._exchange_task_unsub
            _LOGGER.debug("Attempting OAuth code exchange")
            # Note: The callback is invoked with None when the device code has expired
            creds: Credentials | None = None
            if now < expiration_time:
                try:
                    creds = await self._hass.async_add_executor_job(_exchange)
                except FlowExchangeError:
                    _LOGGER.debug("Token not yet ready; trying again later")
                    return
            self._exchange_task_unsub()
            self._exchange_task_unsub = None
            await finished_cb(creds)

        self._exchange_task_unsub = async_track_time_interval(
            self._hass,
            _poll_attempt,
            datetime.timedelta(seconds=self._device_flow_info.interval),
        )


def get_feature_access(hass: HomeAssistant) -> FeatureAccess:
    """Return the desired calendar feature access."""
    # This may be called during config entry setup without integration setup running when there
    # is no google entry in configuration.yaml
    return (
        hass.data.get(DOMAIN, {})
        .get(DATA_CONFIG, {})
        .get(CONF_CALENDAR_ACCESS, DEFAULT_FEATURE_ACCESS)
    )


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
        return self._session.token["access_token"]
