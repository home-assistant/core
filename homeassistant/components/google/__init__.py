"""Support for Google - Calendar Event Devices."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

import aiohttp
from gcal_sync.api import GoogleCalendarService
from gcal_sync.exceptions import ApiException, AuthException
from gcal_sync.model import DateOrDatetime, Event
from oauth2client.file import Storage
import voluptuous as vol
from voluptuous.error import Error as VoluptuousError
import yaml

from homeassistant import config_entries
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_OFFSET,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.typing import ConfigType

from .api import ApiAuthImpl, get_feature_access
from .const import (
    CONF_CALENDAR_ACCESS,
    DATA_CONFIG,
    DATA_SERVICE,
    DEVICE_AUTH_IMPL,
    DOMAIN,
    EVENT_DESCRIPTION,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    EVENT_TYPES_CONF,
    FeatureAccess,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_TRACK_NEW = "track_new_calendar"

CONF_CAL_ID = "cal_id"
CONF_TRACK = "track"
CONF_SEARCH = "search"
CONF_IGNORE_AVAILABILITY = "ignore_availability"
CONF_MAX_RESULTS = "max_results"

DEFAULT_CONF_OFFSET = "!!"

EVENT_CALENDAR_ID = "calendar_id"

NOTIFICATION_ID = "google_calendar_notification"
NOTIFICATION_TITLE = "Google Calendar Setup"
GROUP_NAME_ALL_CALENDARS = "Google Calendar Sensors"

SERVICE_ADD_EVENT = "add_event"

YAML_DEVICES = f"{DOMAIN}_calendars.yaml"

TOKEN_FILE = f".{DOMAIN}.token"

PLATFORMS = ["calendar"]


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                    vol.Optional(CONF_TRACK_NEW, default=True): cv.boolean,
                    vol.Optional(CONF_CALENDAR_ACCESS, default="read_write"): cv.enum(
                        FeatureAccess
                    ),
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

_SINGLE_CALSEARCH_CONFIG = vol.All(
    cv.deprecated(CONF_MAX_RESULTS),
    vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_DEVICE_ID): cv.string,
            vol.Optional(CONF_IGNORE_AVAILABILITY, default=True): cv.boolean,
            vol.Optional(CONF_OFFSET): cv.string,
            vol.Optional(CONF_SEARCH): cv.string,
            vol.Optional(CONF_TRACK): cv.boolean,
            vol.Optional(CONF_MAX_RESULTS): cv.positive_int,  # Now unused
        }
    ),
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAL_ID): cv.string,
        vol.Required(CONF_ENTITIES, None): vol.All(
            cv.ensure_list, [_SINGLE_CALSEARCH_CONFIG]
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

_EVENT_IN_TYPES = vol.Schema(
    {
        vol.Exclusive(EVENT_IN_DAYS, EVENT_TYPES_CONF): cv.positive_int,
        vol.Exclusive(EVENT_IN_WEEKS, EVENT_TYPES_CONF): cv.positive_int,
    }
)

ADD_EVENT_SERVICE_SCHEMA = vol.All(
    cv.has_at_least_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    cv.has_at_most_one_key(EVENT_START_DATE, EVENT_START_DATETIME, EVENT_IN),
    {
        vol.Required(EVENT_CALENDAR_ID): cv.string,
        vol.Required(EVENT_SUMMARY): cv.string,
        vol.Optional(EVENT_DESCRIPTION, default=""): cv.string,
        vol.Inclusive(
            EVENT_START_DATE, "dates", "Start and end dates must both be specified"
        ): cv.date,
        vol.Inclusive(
            EVENT_END_DATE, "dates", "Start and end dates must both be specified"
        ): cv.date,
        vol.Inclusive(
            EVENT_START_DATETIME,
            "datetimes",
            "Start and end datetimes must both be specified",
        ): cv.datetime,
        vol.Inclusive(
            EVENT_END_DATETIME,
            "datetimes",
            "Start and end datetimes must both be specified",
        ): cv.datetime,
        vol.Optional(EVENT_IN): _EVENT_IN_TYPES,
    },
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Google component."""
    if DOMAIN not in config:
        return True

    conf = config.get(DOMAIN, {})
    hass.data[DOMAIN] = {DATA_CONFIG: conf}

    if CONF_CLIENT_ID in conf and CONF_CLIENT_SECRET in conf:
        await async_import_client_credential(
            hass,
            DOMAIN,
            ClientCredential(
                conf[CONF_CLIENT_ID],
                conf[CONF_CLIENT_SECRET],
            ),
            DEVICE_AUTH_IMPL,
        )

    # Import credentials from the old token file into the new way as
    # a ConfigEntry managed by home assistant.
    storage = Storage(hass.config.path(TOKEN_FILE))
    creds = await hass.async_add_executor_job(storage.get)
    if creds and get_feature_access(hass).scope in creds.scopes:
        _LOGGER.debug("Importing configuration entry with credentials")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    "creds": creds,
                },
            )
        )

    _LOGGER.warning(
        "Configuration of Google Calendar in YAML in configuration.yaml is "
        "is deprecated and will be removed in a future release; Your existing "
        "OAuth Application Credentials and access settings have been imported "
        "into the UI automatically and can be safely removed from your "
        "configuration.yaml file"
    )
    if conf.get(CONF_TRACK_NEW) is False:
        # The track_new as False would previously result in new entries
        # in google_calendars.yaml with track set to Fasle which is
        # handled at calendar entity creation time.
        _LOGGER.warning(
            "You must manually set the integration System Options in the "
            "UI to disable newly discovered entities going forward"
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    # Force a token refresh to fix a bug where tokens were persisted with
    # expires_in (relative time delta) and expires_at (absolute time) swapped.
    # A google session token typically only lasts a few days between refresh.
    now = datetime.now()
    if session.token["expires_at"] >= (now + timedelta(days=365)).timestamp():
        session.token["expires_in"] = 0
        session.token["expires_at"] = now.timestamp()
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    if not async_entry_has_scopes(hass, entry):
        raise ConfigEntryAuthFailed(
            "Required scopes are not available, reauth required"
        )
    calendar_service = GoogleCalendarService(
        ApiAuthImpl(async_get_clientsession(hass), session)
    )
    hass.data[DOMAIN][entry.entry_id][DATA_SERVICE] = calendar_service

    if entry.unique_id is None:
        try:
            primary_calendar = await calendar_service.async_get_calendar("primary")
        except AuthException as err:
            raise ConfigEntryAuthFailed from err
        except ApiException as err:
            raise ConfigEntryNotReady from err
        else:
            hass.config_entries.async_update_entry(entry, unique_id=primary_calendar.id)

    # Only expose the add event service if we have the correct permissions
    if get_feature_access(hass, entry) is FeatureAccess.read_write:
        await async_setup_add_event_service(hass, calendar_service)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


def async_entry_has_scopes(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Verify that the config entry desired scope is present in the oauth token."""
    access = get_feature_access(hass, entry)
    token_scopes = entry.data.get("token", {}).get("scope", [])
    return access.scope in token_scopes


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry if the access options change."""
    if not async_entry_has_scopes(hass, entry):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_add_event_service(
    hass: HomeAssistant,
    calendar_service: GoogleCalendarService,
) -> None:
    """Add the service to add events."""

    async def _add_event(call: ServiceCall) -> None:
        """Add a new event to calendar."""
        _LOGGER.warning(
            "The Google Calendar add_event service has been deprecated, and "
            "will be removed in a future Home Assistant release. Please move "
            "calls to the create_event service"
        )

        start: DateOrDatetime | None = None
        end: DateOrDatetime | None = None

        if EVENT_IN in call.data:
            if EVENT_IN_DAYS in call.data[EVENT_IN]:
                now = datetime.now()

                start_in = now + timedelta(days=call.data[EVENT_IN][EVENT_IN_DAYS])
                end_in = start_in + timedelta(days=1)

                start = DateOrDatetime(date=start_in)
                end = DateOrDatetime(date=end_in)

            elif EVENT_IN_WEEKS in call.data[EVENT_IN]:
                now = datetime.now()

                start_in = now + timedelta(weeks=call.data[EVENT_IN][EVENT_IN_WEEKS])
                end_in = start_in + timedelta(days=1)

                start = DateOrDatetime(date=start_in)
                end = DateOrDatetime(date=end_in)

        elif EVENT_START_DATE in call.data and EVENT_END_DATE in call.data:
            start = DateOrDatetime(date=call.data[EVENT_START_DATE])
            end = DateOrDatetime(date=call.data[EVENT_END_DATE])

        elif EVENT_START_DATETIME in call.data and EVENT_END_DATETIME in call.data:
            start_dt = call.data[EVENT_START_DATETIME]
            end_dt = call.data[EVENT_END_DATETIME]
            start = DateOrDatetime(
                date_time=start_dt, timezone=str(hass.config.time_zone)
            )
            end = DateOrDatetime(date_time=end_dt, timezone=str(hass.config.time_zone))

        if start is None or end is None:
            raise ValueError(
                "Missing required fields to set start or end date/datetime"
            )

        await calendar_service.async_create_event(
            call.data[EVENT_CALENDAR_ID],
            Event(
                summary=call.data[EVENT_SUMMARY],
                description=call.data[EVENT_DESCRIPTION],
                start=start,
                end=end,
            ),
        )

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_EVENT, _add_event, schema=ADD_EVENT_SERVICE_SCHEMA
    )


def get_calendar_info(
    hass: HomeAssistant, calendar: Mapping[str, Any]
) -> dict[str, Any]:
    """Convert data from Google into DEVICE_SCHEMA."""
    calendar_info: dict[str, Any] = DEVICE_SCHEMA(
        {
            CONF_CAL_ID: calendar["id"],
            CONF_ENTITIES: [
                {
                    CONF_NAME: calendar["summary"],
                    CONF_DEVICE_ID: generate_entity_id(
                        "{}", calendar["summary"], hass=hass
                    ),
                }
            ],
        }
    )
    return calendar_info


def load_config(path: str) -> dict[str, Any]:
    """Load the google_calendar_devices.yaml."""
    calendars = {}
    try:
        with open(path, encoding="utf8") as file:
            data = yaml.safe_load(file)
            for calendar in data:
                try:
                    calendars.update({calendar[CONF_CAL_ID]: DEVICE_SCHEMA(calendar)})
                except VoluptuousError as exception:
                    # keep going
                    _LOGGER.warning("Calendar Invalid Data: %s", exception)
    except FileNotFoundError as err:
        _LOGGER.debug("Error reading calendar configuration: %s", err)
        # When YAML file could not be loaded/did not contain a dict
        return {}

    return calendars


def update_config(path: str, calendar: dict[str, Any]) -> None:
    """Write the google_calendar_devices.yaml."""
    try:
        with open(path, "a", encoding="utf8") as out:
            out.write("\n")
            yaml.dump([calendar], out, default_flow_style=False)
    except FileNotFoundError as err:
        _LOGGER.debug("Error persisting calendar configuration: %s", err)
