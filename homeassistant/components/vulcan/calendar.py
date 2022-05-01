"""Support for Vulcan Calendar platform."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from aiohttp import ClientConnectorError
from vulcan._utils import VulcanAPIException

from homeassistant.components.calendar import (
    ENTITY_ID_FORMAT,
    CalendarEntity,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from . import DOMAIN
from .const import DEFAULT_SCAN_INTERVAL
from .fetch_data import get_lessons, get_student_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    VulcanCalendarEntity.MIN_TIME_BETWEEN_UPDATES = timedelta(
        minutes=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
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
            VulcanCalendarEntity(
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


class VulcanCalendarEntity(CalendarEntity):
    """A calendar entity."""

    def __init__(self, client, data, entity_id) -> None:
        """Create the Calendar entity."""
        self.student_info = data["student_info"]
        self._event: CalendarEvent | None = None
        self.client = client
        self.entity_id = entity_id
        self._unique_id = f"vulcan_calendar_{self.student_info['id']}"
        self.service_available = True

        if data["students_number"] == 1:
            self._attr_name = "Vulcan calendar"
            self.device_name = "Calendar"
        else:
            self._attr_name = f"Vulcan calendar - {self.student_info['full_name']}"
            self.device_name = f"{self.student_info['full_name']}: Calendar"
        self._attr_unique_id = f"vulcan_calendar_{self.student_info['id']}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"calendar_{self.student_info['id']}")},
            "entry_type": DeviceEntryType.SERVICE,
            "name": self.device_name,
            "model": f"{self.student_info['full_name']} - {self.student_info['class']} {self.student_info['school']}",
            "manufacturer": "Uonet +",
            "configuration_url": f"https://uonetplus.vulcan.net.pl/{self.student_info['symbol']}",
        }

    MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=DEFAULT_SCAN_INTERVAL)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(self, hass, start_date, end_date) -> list[CalendarEvent]:
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
                    "The certificate is not authorized, please authorize integration again"
                )
                raise ConfigEntryAuthFailed from err
            _LOGGER.error("An API error has occurred: %s", err)
            events = []
        except ClientConnectorError as err:
            if self.service_available:
                _LOGGER.warning(
                    "Connection error - please check your internet connection: %s", err
                )
            events = []

        event_list = []
        for item in events:
            event = CalendarEvent(
                start=datetime.combine(item["date"], item["time"].from_),
                end=datetime.combine(item["date"], item["time"].to),
                summary=item["lesson"],
                location=item["room"],
                description=item["teacher"],
            )

            event_list.append(event)

        return event_list

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest data."""

        try:
            events = await get_lessons(self.client)

            if not self.service_available:
                _LOGGER.info("Restored connection with API")
                self.service_available = True

            if events == []:
                events = await get_lessons(
                    self.client,
                    date_to=date.today() + timedelta(days=7),
                )
                if events == []:
                    self._event = None
                    return
        except VulcanAPIException as err:
            if str(err) == "The certificate is not authorized.":
                _LOGGER.error(
                    "The certificate is not authorized, please authorize integration again"
                )
                raise ConfigEntryAuthFailed from err
            _LOGGER.error("An API error has occurred: %s", err)
            return
        except ClientConnectorError as err:
            if self.service_available:
                _LOGGER.warning(
                    "Connection error - please check your internet connection: %s", err
                )
                self.service_available = False
            return

        new_event = min(
            events,
            key=lambda d: (
                datetime.combine(d["date"], d["time"].to) < datetime.now(),
                abs(datetime.combine(d["date"], d["time"].to) - datetime.now()),
            ),
        )
        self._event = CalendarEvent(
            start=datetime.combine(new_event["date"], new_event["time"].from_),
            end=datetime.combine(new_event["date"], new_event["time"].to),
            summary=new_event["lesson"],
            location=new_event["room"],
            description=new_event["teacher"],
        )
