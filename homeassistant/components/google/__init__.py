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
import voluptuous as vol
import yaml

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_OFFSET,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id

from .api import ApiAuthImpl, get_feature_access
from .const import (
    DATA_SERVICE,
    DATA_STORE,
    DOMAIN,
    EVENT_DESCRIPTION,
    EVENT_END_DATE,
    EVENT_END_DATETIME,
    EVENT_IN,
    EVENT_IN_DAYS,
    EVENT_IN_WEEKS,
    EVENT_LOCATION,
    EVENT_START_DATE,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    EVENT_TYPES_CONF,
    FeatureAccess,
)
from .store import LocalCalendarStore

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

SERVICE_ADD_EVENT = "add_event"

YAML_DEVICES = f"{DOMAIN}_calendars.yaml"

PLATFORMS = [Platform.CALENDAR]


CONFIG_SCHEMA = vol.Schema(cv.removed(DOMAIN), extra=vol.ALLOW_EXTRA)


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
        vol.Optional(EVENT_LOCATION, default=""): cv.string,
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    # Validate google_calendars.yaml (if present) as soon as possible to return
    # helpful error messages.
    try:
        await hass.async_add_executor_job(load_config, hass.config.path(YAML_DEVICES))
    except vol.Invalid as err:
        _LOGGER.error("Configuration error in %s: %s", YAML_DEVICES, str(err))
        return False

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
    hass.data[DOMAIN][entry.entry_id][DATA_STORE] = LocalCalendarStore(
        hass, entry.entry_id
    )

    if entry.unique_id is None:
        try:
            primary_calendar = await calendar_service.async_get_calendar("primary")
        except AuthException as err:
            raise ConfigEntryAuthFailed from err
        except ApiException as err:
            raise ConfigEntryNotReady from err

        hass.config_entries.async_update_entry(entry, unique_id=primary_calendar.id)

    # Only expose the add event service if we have the correct permissions
    if get_feature_access(hass, entry) is FeatureAccess.read_write:
        await async_setup_add_event_service(hass, calendar_service)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a local storage."""
    store = LocalCalendarStore(hass, entry.entry_id)
    await store.async_remove()


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
        event = Event(
            summary=call.data[EVENT_SUMMARY],
            description=call.data[EVENT_DESCRIPTION],
            start=start,
            end=end,
        )
        if location := call.data.get(EVENT_LOCATION):
            event.location = location
        try:
            await calendar_service.async_create_event(
                call.data[EVENT_CALENDAR_ID],
                event,
            )
        except ApiException as err:
            raise HomeAssistantError(str(err)) from err

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
            data = yaml.safe_load(file) or []
            for calendar in data:
                calendars[calendar[CONF_CAL_ID]] = DEVICE_SCHEMA(calendar)
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
