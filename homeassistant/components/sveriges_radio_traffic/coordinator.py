"""Example integration using DataUpdateCoordinator."""

from dataclasses import dataclass
from datetime import timedelta
import logging

import async_timeout
import defusedxml.ElementTree as defET
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrafficData:
    """Dataclass for Trafikverket Train data."""

    title: str
    message: str
    time: float
    exactlocation: str


# We have this in sensor.py i think
# async def async_setup_entry(hass, entry, async_add_entities):
#     """Config entry example."""
#     # assuming API object stored here by __init__.py
#     my_api = hass.data[DOMAIN][entry.entry_id]
#     coordinator = MyCoordinator(hass, my_api)

#     # Fetch initial data so we have data when entities subscribe
#     #
#     # If the refresh fails, async_config_entry_first_refresh will
#     # raise ConfigEntryNotReady and setup will try again later
#     #
#     # If you do not want to retry setup on failure, use
#     # coordinator.async_refresh() instead
#     #
#     await coordinator.async_config_entry_first_refresh()

#     async_add_entities(
#         MyEntity(coordinator, idx) for idx, ent in enumerate(coordinator.data)
#     )


class SverigesRadioTrafficCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass: HomeAssistant, area) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="My sensor",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=10),
        )
        self.traffic_area = area

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.

            states = await self._get_traffic_info()
            return states

            # listening_idx = set(self.async_contexts())
            # return await self.my_api.fetch_data(listening_idx)

    async def _get_traffic_info(self) -> TrafficData | None:
        """Fetch traffic information from specific area."""
        # Obs! Below is dangerous if traffic_area isn't set, add security
        response = requests.get(
            "http://api.sr.se/api/v2/traffic/messages?trafficareaname="
            + self.traffic_area,
            timeout=10,
        )
        defET.fromstring(response.content)

        states = TrafficData(
            title="Title", message="message", time=13.5, exactlocation="Place"
        )

        return states

        # return_string = ""
        # if self._attr_name == CONF_AREA_NAME:
        #     return self.traffic_area

        # for message in tree.findall(".//message"):
        #     return_string = message.find(self.api_name).text

        # if self.api_name == DATE:
        #     (date, _, time) = return_string.partition("T")
        #     return_string = time[0:5] + ", " + date

        # return return_string


# class MyEntity(CoordinatorEntity, SensorEntity):
#     """An entity using CoordinatorEntity.

#     The CoordinatorEntity class provides:
#       should_poll
#       async_update
#       async_added_to_hass
#       available

#     """

#     def __init__(self, coordinator, idx):
#         """Pass coordinator to CoordinatorEntity."""
#         super().__init__(coordinator, context=idx)
#         self.idx = idx

#     @callback
#     def _handle_coordinator_update(self) -> None:
#         """Handle updated data from the coordinator."""
#         self._attr_is_on = self.coordinator.data[self.idx]["state"]
#         self.async_write_ha_state()

#     async def async_turn_on(self, **kwargs):
#         """Turn the light on.

#         Example method how to request data updates.
#         """
#         # Do the turning on.
#         # ...

#         # Update the data
#         await self.coordinator.async_request_refresh()
