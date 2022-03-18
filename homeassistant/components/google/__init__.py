"""Support for Google - Calendar Event Devices."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import logging
from typing import Any

from httplib2.error import ServerNotFoundError
from oauth2client.file import Storage
import voluptuous as vol
from voluptuous.error import Error as VoluptuousError
import yaml

from homeassistant import config_entries
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
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.typing import ConfigType

from . import config_flow
from .api import DeviceAuth, GoogleCalendarService
from .const import (
    CONF_CALENDAR_ACCESS,
    DATA_CONFIG,
    DATA_SERVICE,
    DISCOVER_CALENDAR,
    DOMAIN,
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
EVENT_DESCRIPTION = "description"
EVENT_END_CONF = "end"
EVENT_END_DATE = "end_date"
EVENT_END_DATETIME = "end_date_time"
EVENT_IN = "in"
EVENT_IN_DAYS = "days"
EVENT_IN_WEEKS = "weeks"
EVENT_START_CONF = "start"
EVENT_START_DATE = "start_date"
EVENT_START_DATETIME = "start_date_time"
EVENT_SUMMARY = "summary"
EVENT_TYPES_CONF = "event_types"

NOTIFICATION_ID = "google_calendar_notification"
NOTIFICATION_TITLE = "Google Calendar Setup"
GROUP_NAME_ALL_CALENDARS = "Google Calendar Sensors"

SERVICE_SCAN_CALENDARS = "scan_for_calendars"
SERVICE_FOUND_CALENDARS = "found_calendar"
SERVICE_ADD_EVENT = "add_event"

YAML_DEVICES = f"{DOMAIN}_calendars.yaml"

TOKEN_FILE = f".{DOMAIN}.token"

PLATFORMS = ["calendar"]


CONFIG_SCHEMA = vol.Schema(
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

ADD_EVENT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_CALENDAR_ID): cv.string,
        vol.Required(EVENT_SUMMARY): cv.string,
        vol.Optional(EVENT_DESCRIPTION, default=""): cv.string,
        vol.Exclusive(EVENT_START_DATE, EVENT_START_CONF): cv.date,
        vol.Exclusive(EVENT_END_DATE, EVENT_END_CONF): cv.date,
        vol.Exclusive(EVENT_START_DATETIME, EVENT_START_CONF): cv.datetime,
        vol.Exclusive(EVENT_END_DATETIME, EVENT_END_CONF): cv.datetime,
        vol.Exclusive(EVENT_IN, EVENT_START_CONF, EVENT_END_CONF): _EVENT_IN_TYPES,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Google component."""
    conf = config.get(DOMAIN, {})
    hass.data[DOMAIN] = {DATA_CONFIG: conf}
    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        DeviceAuth(
            hass,
            conf[CONF_CLIENT_ID],
            conf[CONF_CLIENT_SECRET],
        ),
    )

    # Import credentials from the old token file into the new way as
    # a ConfigEntry managed by home assistant.
    storage = Storage(hass.config.path(TOKEN_FILE))
    creds = await hass.async_add_executor_job(storage.get)
    if creds and conf[CONF_CALENDAR_ACCESS].scope in creds.scopes:
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
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    assert isinstance(implementation, DeviceAuth)
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    required_scope = hass.data[DOMAIN][DATA_CONFIG][CONF_CALENDAR_ACCESS].scope
    if required_scope not in session.token.get("scope", []):
        raise ConfigEntryAuthFailed(
            "Required scopes are not available, reauth required"
        )
    calendar_service = GoogleCalendarService(hass, session)
    hass.data[DOMAIN][DATA_SERVICE] = calendar_service

    await async_setup_services(hass, hass.data[DOMAIN][DATA_CONFIG], calendar_service)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_setup_services(
    hass: HomeAssistant,
    config: ConfigType,
    calendar_service: GoogleCalendarService,
) -> None:
    """Set up the service listeners."""

    created_calendars = set()
    calendars = await hass.async_add_executor_job(
        load_config, hass.config.path(YAML_DEVICES)
    )

    async def _found_calendar(call: ServiceCall) -> None:
        calendar = get_calendar_info(hass, call.data)
        calendar_id = calendar[CONF_CAL_ID]

        if calendar_id in created_calendars:
            return
        created_calendars.add(calendar_id)

        # Populate the yaml file with all discovered calendars
        if calendar_id not in calendars:
            calendars[calendar_id] = calendar
            await hass.async_add_executor_job(
                update_config, hass.config.path(YAML_DEVICES), calendar
            )
        else:
            # Prefer entity/name information from yaml, overriding api
            calendar = calendars[calendar_id]
        async_dispatcher_send(hass, DISCOVER_CALENDAR, calendar)

    hass.services.async_register(DOMAIN, SERVICE_FOUND_CALENDARS, _found_calendar)

    async def _scan_for_calendars(call: ServiceCall) -> None:
        """Scan for new calendars."""
        try:
            calendars = await calendar_service.async_list_calendars()
        except ServerNotFoundError as err:
            raise HomeAssistantError(str(err)) from err
        tasks = []
        for calendar in calendars:
            calendar[CONF_TRACK] = config[CONF_TRACK_NEW]
            tasks.append(
                hass.services.async_call(DOMAIN, SERVICE_FOUND_CALENDARS, calendar)
            )
        await asyncio.gather(*tasks)

    hass.services.async_register(DOMAIN, SERVICE_SCAN_CALENDARS, _scan_for_calendars)

    async def _add_event(call: ServiceCall) -> None:
        """Add a new event to calendar."""
        start = {}
        end = {}

        if EVENT_IN in call.data:
            if EVENT_IN_DAYS in call.data[EVENT_IN]:
                now = datetime.now()

                start_in = now + timedelta(days=call.data[EVENT_IN][EVENT_IN_DAYS])
                end_in = start_in + timedelta(days=1)

                start = {"date": start_in.strftime("%Y-%m-%d")}
                end = {"date": end_in.strftime("%Y-%m-%d")}

            elif EVENT_IN_WEEKS in call.data[EVENT_IN]:
                now = datetime.now()

                start_in = now + timedelta(weeks=call.data[EVENT_IN][EVENT_IN_WEEKS])
                end_in = start_in + timedelta(days=1)

                start = {"date": start_in.strftime("%Y-%m-%d")}
                end = {"date": end_in.strftime("%Y-%m-%d")}

        elif EVENT_START_DATE in call.data:
            start = {"date": str(call.data[EVENT_START_DATE])}
            end = {"date": str(call.data[EVENT_END_DATE])}

        elif EVENT_START_DATETIME in call.data:
            start_dt = str(
                call.data[EVENT_START_DATETIME].strftime("%Y-%m-%dT%H:%M:%S")
            )
            end_dt = str(call.data[EVENT_END_DATETIME].strftime("%Y-%m-%dT%H:%M:%S"))
            start = {"dateTime": start_dt, "timeZone": str(hass.config.time_zone)}
            end = {"dateTime": end_dt, "timeZone": str(hass.config.time_zone)}

        await calendar_service.async_create_event(
            call.data[EVENT_CALENDAR_ID],
            {
                "summary": call.data[EVENT_SUMMARY],
                "description": call.data[EVENT_DESCRIPTION],
                "start": start,
                "end": end,
            },
        )

    # Only expose the add event service if we have the correct permissions
    if config.get(CONF_CALENDAR_ACCESS) is FeatureAccess.read_write:
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
                    CONF_TRACK: calendar["track"],
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
