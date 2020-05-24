"""Support for a monitoring station."""
from datetime import timedelta
import logging

from aioeafm import get_station
import aiohttp

from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


class Station:
    """A collection of gauges at a flood monitoring station."""

    def __init__(self, hass, entry):
        """Initialise the station."""
        self.hass = hass
        self.entry = entry
        self.station = entry.data["station"]
        self.measurements = {}
        self.available = True
        self._poller_remover = None
        self._async_add_entities = None

    @property
    def is_polling(self):
        """Is the station being actively monitored."""
        return self._poller_remover is not None

    async def async_start(self):
        """Start polling the API."""
        self._poller_remover = async_track_time_interval(
            self.hass, self.async_poll, SCAN_INTERVAL
        )
        await self.hass.config_entries.async_forward_entry_setup(self.entry, "sensor")
        await self.async_poll()

    @callback
    def async_platform_loaded(self, platform, async_add_entity):
        """Register a platform that this station can create entities in."""
        # We can't add entities until we get an async_add_entities from the right platform
        # Right now we only have a sensors platform.
        self._async_add_entities = async_add_entity

    async def async_stop(self):
        """Stop polling the API."""
        if self._poller_remover:
            self._poller_remover()
            self._poller_remover = None
        return await self.hass.config_entries.async_forward_entry_unload(
            self.entry, "sensor"
        )

    @callback
    def async_set_unavailable(self):
        """Mark measures as unavailable."""
        self.available = False
        for measure in self.measurements.values():
            measure.async_set_unavailable()

    async def async_poll(self, now=None):
        """Get the latest measurements for a station."""
        session = async_get_clientsession(hass=self.hass)

        try:
            data = await get_station(session, self.station)
        except aiohttp.ClientConnectionError:
            if self.available:
                _LOGGER.error(
                    "Unable to reach the flood monitoring API. It looks like a connectivity issue. Home Assistant will keep trying in the background."
                )
                self.async_set_unavailable()
            return
        except aiohttp.ClientResponseError:
            if self.available:
                _LOGGER.error(
                    "Unable to reach the flood monitoring API. The server returned an error. Home Assistant will keep trying in the background."
                )
                self.async_set_unavailable()
            return

        for measure in data["measures"]:
            if measure["@id"] not in self.measurements and self._async_add_entities:
                if "latestReading" not in measure:
                    # Don't create a sensor entity for a gauge that isn't available
                    continue
                self.measurements[measure["@id"]] = self._async_add_entities(
                    data, measure
                )
                continue

            measurement = self.measurements[measure["@id"]]
            measurement.async_process_update(measure)

        self.available = True
