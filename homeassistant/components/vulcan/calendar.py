"""Support for Vulcan Calendar."""
import copy
from datetime import date, datetime, timedelta
import logging

from aiohttp import ClientConnectorError
from vulcan._utils import VulcanAPIException

from homeassistant.components.calendar import ENTITY_ID_FORMAT, CalendarEventDevice
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.template import DATE_STR_FORMAT
from homeassistant.util import Throttle, dt

from . import DOMAIN
from .const import DEFAULT_SCAN_INTERVAL
from .fetch_data import get_lessons, get_student_info

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=DEFAULT_SCAN_INTERVAL)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the calendar platform for event devices."""
    global MIN_TIME_BETWEEN_UPDATES
    MIN_TIME_BETWEEN_UPDATES = (
        timedelta(minutes=config_entry.options.get(CONF_SCAN_INTERVAL))
        if config_entry.options.get(CONF_SCAN_INTERVAL) is not None
        else MIN_TIME_BETWEEN_UPDATES
    )
    client = hass.data[DOMAIN][config_entry.entry_id]
    data = {
        "student_info": await get_student_info(
            client, config_entry.data.get("student_id")
        ),
        "students_number": hass.data[DOMAIN]["students_number"],
    }
    async_add_entities(
        [
            VulcanCalendarEventDevice(
                client,
                data,
                generate_entity_id(
                    ENTITY_ID_FORMAT,
                    f"vulcan_calendar_{data['student_info']['full_name']}",
                    hass=hass,
                ),
            )
        ],
    )


class VulcanCalendarEventDevice(CalendarEventDevice):
    """A calendar event device."""

    def __init__(self, client, data, entity_id):
        """Create the Calendar event device."""
        self.student_info = data["student_info"]
        self.data = VulcanCalendarData(
            client,
            self.student_info,
        )
        self._event = None
        self.entity_id = entity_id
        self._unique_id = f"vulcan_calendar_{self.student_info['id']}"

        if data["students_number"] == 1:
            name = ""
            self.device_name = "Calendar"
        else:
            name = f" - {self.student_info['full_name']}"
            self.device_name = f"{self.student_info['full_name']}: Calendar"
        self._name = f"Vulcan calendar{name}"

    @property
    def unique_id(self):
        """Return unique id."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, f"calendar_{self.student_info['id']}")},
            "manufacturer": "Uonet +",
            "model": f"{self.student_info['class']} {self.student_info['school']}",
            "name": self.device_name,
            "entry_type": "service",
        }

    @property
    def event(self):
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)

    async def async_update(self):
        """Update event data."""
        await self.data.async_update()
        event = copy.deepcopy(self.data.event)
        if event is None:
            self._event = event
            return
        event["start"] = {
            "dateTime": datetime.combine(event["date"], event["time"].from_)
            .astimezone(dt.DEFAULT_TIME_ZONE)
            .isoformat()
        }
        event["end"] = {
            "dateTime": datetime.combine(event["date"], event["time"].to)
            .astimezone(dt.DEFAULT_TIME_ZONE)
            .isoformat()
        }
        self._event = event


class VulcanCalendarData:
    """Class to utilize calendar service object to get next event."""

    def __init__(self, client, student_info):
        """Set up how we are going to search the Vulcan calendar."""
        self.client = client
        self.student_info = student_info
        self.event = None
        self._available = True

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        try:
            events = await get_lessons(
                self.client,
                date_from=start_date,
                date_to=end_date,
            )
        except VulcanAPIException as err:
            if str(err) == "The certificate is not authorized.":
                _LOGGER.error(
                    "The certificate is not authorized, please authorize integration again."
                )
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "reauth"},
                    )
                )
            else:
                _LOGGER.error("An API error has occurred: %s", err)
            events = []
        except ClientConnectorError as err:
            if self._available:
                _LOGGER.warning(
                    "Connection error - please check your internet connection: %s", err
                )
            events = []

        event_list = []
        for item in events:
            event = {
                "uid": item["id"],
                "start": {
                    "dateTime": datetime.combine(
                        item["date"], item["time"].from_
                    ).strftime(DATE_STR_FORMAT)
                },
                "end": {
                    "dateTime": datetime.combine(
                        item["date"], item["time"].to
                    ).strftime(DATE_STR_FORMAT)
                },
                "summary": item["lesson"],
                "location": item["room"],
                "description": item["teacher"],
            }

            event_list.append(event)

        return event_list

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data."""

        try:
            events = await get_lessons(self.client)

            if not self._available:
                _LOGGER.info("Restored connection with API")
                self._available = True

            if events == []:
                events = await get_lessons(
                    self.client,
                    date_to=date.today() + timedelta(days=7),
                )
                if events == []:
                    self.event = None
                    return
        except VulcanAPIException as err:
            if str(err) == "The certificate is not authorized.":
                _LOGGER.error(
                    "The certificate is not authorized, please authorize integration again."
                )
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "reauth"},
                    )
                )
            else:
                _LOGGER.error("An API error has occurred: %s", err)
            return
        except ClientConnectorError as err:
            if self._available:
                _LOGGER.warning(
                    "Connection error - please check your internet connection: %s", err
                )
                self._available = False
            return

        new_event = min(
            events,
            key=lambda d: (
                datetime.combine(d["date"], d["time"].to) < datetime.now(),
                abs(datetime.combine(d["date"], d["time"].to) - datetime.now()),
            ),
        )
        self.event = {
            "uid": new_event["id"],
            "date": new_event["date"],
            "time": new_event["time"],
            "summary": new_event["lesson"],
            "location": new_event["room"],
            "description": new_event["teacher"],
        }
