"""Client library for talking to Google APIs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime
import logging
from typing import Any

from googleapiclient import discovery as google_discovery
import oauth2client
from oauth2client.client import (
    Credentials,
    DeviceFlowInfo,
    FlowExchangeError,
    OAuth2Credentials,
    OAuth2DeviceCodeError,
    OAuth2WebServerFlow,
)

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt

from .const import CONF_CALENDAR_ACCESS, DATA_CONFIG, DEVICE_AUTH_IMPL, DOMAIN

_LOGGER = logging.getLogger(__name__)

EVENT_PAGE_SIZE = 100
EXCHANGE_TIMEOUT_SECONDS = 60


class OAuthError(Exception):
    """OAuth related error."""


class TokenNotReady(Exception):
    """Raised when the token exchange is not yet ready, and should be attempted again."""


class DeviceAuth(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """OAuth implementation for Device Auth."""

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str) -> None:
        """Initialize InstalledAppAuth."""
        super().__init__(
            hass,
            DEVICE_AUTH_IMPL,
            client_id,
            client_secret,
            oauth2client.GOOGLE_AUTH_URI,
            oauth2client.GOOGLE_TOKEN_URI,
        )

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve a Google API Credentials object to Home Assistant token."""
        creds: Credentials = external_data["creds"]
        return {
            "access_token": creds.access_token,
            "refresh_token": creds.refresh_token,
            "scope": " ".join(creds.scopes),
            "token_type": "Bearer",
            "expires_in": creds.token_expiry.timestamp(),
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

        async def _poll_attempt(now: datetime.datetime):
            assert self._exchange_task_unsub
            _LOGGER.debug("Attempting OAuth code exchange")
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


async def async_create_device_flow(hass: HomeAssistant) -> DeviceFlow:
    """Create a new Device flow."""
    conf = hass.data[DOMAIN][DATA_CONFIG]
    oauth_flow = OAuth2WebServerFlow(
        client_id=conf[CONF_CLIENT_ID],
        client_secret=conf[CONF_CLIENT_SECRET],
        scope=conf[CONF_CALENDAR_ACCESS].scope,
        redirect_uri="",
    )
    try:
        device_flow_info = await hass.async_add_executor_job(
            oauth_flow.step1_get_device_and_user_codes
        )
    except OAuth2DeviceCodeError as err:
        raise OAuthError(str(err)) from err
    return DeviceFlow(hass, oauth_flow, device_flow_info)


def _async_google_creds(hass: HomeAssistant, token: dict[str, Any]) -> Credentials:
    """Convert a Home Assistant token to a Google API Credentials object."""
    conf = hass.data[DOMAIN][DATA_CONFIG]
    return OAuth2Credentials(
        access_token=token["access_token"],
        client_id=conf[CONF_CLIENT_ID],
        client_secret=conf[CONF_CLIENT_SECRET],
        refresh_token=token["refresh_token"],
        token_expiry=token["expires_at"],
        token_uri=oauth2client.GOOGLE_TOKEN_URI,
        scopes=[conf[CONF_CALENDAR_ACCESS].scope],
        user_agent=None,
    )


def _api_time_format(time: datetime.datetime | None) -> str | None:
    """Convert a datetime to the api string format."""
    return time.isoformat("T") if time else None


class GoogleCalendarService:
    """Calendar service interface to Google."""

    def __init__(
        self, hass: HomeAssistant, session: config_entry_oauth2_flow.OAuth2Session
    ) -> None:
        """Init the Google Calendar service."""
        self._hass = hass
        self._session = session

    async def _async_get_service(self) -> google_discovery.Resource:
        """Get the calendar service with valid credetnails."""
        await self._session.async_ensure_token_valid()
        creds = _async_google_creds(self._hass, self._session.token)
        return google_discovery.build(
            "calendar", "v3", credentials=creds, cache_discovery=False
        )

    async def async_list_calendars(
        self,
    ) -> list[dict[str, Any]]:
        """Return the list of calendars the user has added to their list."""
        service = await self._async_get_service()

        def _list_calendars() -> list[dict[str, Any]]:
            cal_list = service.calendarList()  # pylint: disable=no-member
            return cal_list.list().execute()["items"]

        return await self._hass.async_add_executor_job(_list_calendars)

    async def async_create_event(
        self, calendar_id: str, event: dict[str, Any]
    ) -> dict[str, Any]:
        """Return the list of calendars the user has added to their list."""
        service = await self._async_get_service()

        def _create_event() -> dict[str, Any]:
            events = service.events()  # pylint: disable=no-member
            return events.insert(calendarId=calendar_id, body=event).execute()

        return await self._hass.async_add_executor_job(_create_event)

    async def async_list_events(
        self,
        calendar_id: str,
        start_time: datetime.datetime | None = None,
        end_time: datetime.datetime | None = None,
        search: str | None = None,
        page_token: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Return the list of events."""
        service = await self._async_get_service()

        def _list_events() -> tuple[list[dict[str, Any]], str | None]:
            events = service.events()  # pylint: disable=no-member
            result = events.list(
                calendarId=calendar_id,
                timeMin=_api_time_format(start_time if start_time else dt.now()),
                timeMax=_api_time_format(end_time),
                q=search,
                maxResults=EVENT_PAGE_SIZE,
                pageToken=page_token,
                singleEvents=True,  # Flattens recurring events
                orderBy="startTime",
            ).execute()
            return (result["items"], result.get("nextPageToken"))

        return await self._hass.async_add_executor_job(_list_events)
