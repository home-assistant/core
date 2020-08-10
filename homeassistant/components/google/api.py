"""API for Google bound to Home Assistant OAuth."""

from abc import ABC
from asyncio import run_coroutine_threadsafe
import datetime
import logging
from typing import Dict, List

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
)

from .const import GOOGLE_CALENDAR_API, GOOGLE_PEOPLE_API, SCOPES

_LOGGER = logging.getLogger(__name__)


class GoogleAPI(ABC):
    """
    Google APIs & Services.

    https://console.developers.google.com/apis/dashboard
    """

    def __init__(self, client_id: str, client_secret: str, info: Dict):
        """Initialize Google API."""
        info["client_id"] = client_id
        info["client_secret"] = client_secret
        scopes = info.get("scope", "").split(" ")
        self.creds = Credentials.from_authorized_user_info(info, scopes)
        self.calendar = None
        self.people = None
        self.info = info

    def setup(self) -> bool:
        """Set up Google APIs and Services."""

        if self.creds.has_scopes(SCOPES[GOOGLE_CALENDAR_API]):
            self.calendar = GoogleCalendarAPI(self.creds)

        if self.creds.has_scopes(SCOPES[GOOGLE_PEOPLE_API]):
            self.people = GooglePeopleAPI(self.creds)

        return True


class GoogleCalendarAPI:
    """
    Google Calendar API.

    https://developers.google.com/calendar/auth
    https://developers.google.com/calendar
    https://developers.google.com/resources/api-libraries/documentation/calendar/v3/python/latest/index.html
    https://developers.google.com/calendar/concepts/events-calendars#calendar_and_calendar_list
    TODO: Push updates # pylint: disable=fixme
    https://developers.google.com/calendar/v3/push
    """

    def __init__(self, creds: Credentials):
        """Initialize Google Calendar API."""
        self._api = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_calendars(self) -> List:
        """
        List calendars.

        https://developers.google.com/calendar/v3/reference/calendarList/list
        """
        calendars = (
            self._api.calendarList().list().execute()  # pylint: disable=maybe-no-member
        )
        return calendars.get("items", [])

    def list_events(self, calendar_id="primary", count=None) -> List:
        """
        List events.

        https://developers.google.com/calendar/v3/reference/events/list
        """
        # TODO: List events for this calendar month # pylint: disable=fixme
        # TODO: List events for the next 7 days # pylint: disable=fixme
        # TODO: List events for today # pylint: disable=fixme
        # TODO: List x scheduled/upcoming events # pylint: disable=fixme
        date_start = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )  # 'Z' indicates UTC time
        date_end = (
            datetime.datetime.utcnow().isoformat() + "Z"
        )  # 'Z' indicates UTC time
        events = (
            self._api.events()  # pylint: disable=maybe-no-member
            .list(
                calendarId=calendar_id,
                timeMin=date_start,
                timeMax=date_end,
                maxResults=count,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        return events.get("items", [])


class GooglePeopleAPI:
    """
    Google People API.

    https://developers.google.com/people
    http://googleapis.github.io/google-api-python-client/docs/dyn/people_v1.people.html
    """

    def __init__(self, creds: Credentials):
        """Initialize Google People API."""
        self._api = build("people", "v1", credentials=creds, cache_discovery=False)

    def list_contacts(self, count=None) -> List:
        """
        List contacts.

        https://developers.google.com/people/api/rest/v1/people.connections/list
        """
        contacts = []
        page_token = ""
        while True:
            results = (
                self._api.people()  # pylint: disable=maybe-no-member
                .connections()
                .list(
                    sortOrder="LAST_NAME_ASCENDING",
                    resourceName="people/me",
                    pageSize=count,
                    personFields="birthdays,events,names",
                    pageToken=page_token,
                )
                .execute()
            )
            contacts.extend(results.get("connections", []))

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        return contacts


class ConfigEntryAuth(GoogleAPI):
    """Provide authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        implementation: AbstractOAuth2Implementation,
    ):
        """Initialize API ConfigEntryAuth."""
        self.hass = hass
        self.config_entry = entry
        self.session = OAuth2Session(hass, entry, implementation)
        client_id = entry.data.get(CONF_CLIENT_ID)
        client_secret = entry.data.get(CONF_CLIENT_SECRET)

        super().__init__(client_id, client_secret, self.session.token)

    def refresh_tokens(self) -> dict:
        """Refresh and return new Google tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        return self.session.token
