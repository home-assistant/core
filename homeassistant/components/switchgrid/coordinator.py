from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TypedDict

import aiohttp
import async_timeout

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class Event(TypedDict):
    eventId: str
    startUtc: datetime
    endUtc: datetime
    summary: str
    description: str


@dataclass
class SwitchgridEventsResponse(TypedDict):
    events: list[Event]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform for entity."""
    coordinator: SwitchgridCoordinator = SwitchgridCoordinator(hass, config_entry)
    async_add_entities([SwitchgridCoordinator(coordinator, config_entry)])


class SwitchgridCoordinator(DataUpdateCoordinator[list[Event]]):
    """Coordinator for updating data from the Switchgrid API."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        self._config_entry = config_entry
        super().__init__(
            hass,
            _LOGGER,
            name="Switchgrid Events Coordinator",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(10):
                url = "https://licarth.eu.ngrok.io/api/homeassistant/events"
                # url = "https://app.switchgrid.tech/api/homeassistant/events"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        response_object = await response.json()
                        events = list(
                            map(
                                lambda event: Event(
                                    eventId=event["eventId"],
                                    startUtc=datetime.fromisoformat(event["startUtc"]),
                                    endUtc=datetime.fromisoformat(event["endUtc"]),
                                    summary=event["summary"],
                                    description=event["description"],
                                ),
                                response_object["events"],
                            )
                        )
                        print(events)
                        return SwitchgridEventsResponse(events=events)

        except aiohttp.ClientError as error:
            raise UpdateFailed(error) from error

    def next_event(self):
        now = dt_util.now()
        return list(
            filter(
                lambda event: event["startUtc"] > now,
                self.data["events"],
            )
        )[0]
