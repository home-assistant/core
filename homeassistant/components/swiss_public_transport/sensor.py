"""Support for transport.opendata.ch."""
from __future__ import annotations

from datetime import timedelta
import logging

from opendata_transport.exceptions import OpendataTransportError

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_DELAY,
    ATTR_DEPARTURE_TIME1,
    ATTR_DEPARTURE_TIME2,
    ATTR_DURATION,
    ATTR_PLATFORM,
    ATTR_REMAINING_TIME,
    ATTR_START,
    ATTR_TARGET,
    ATTR_TRAIN_NUMBER,
    ATTR_TRANSFERS,
    CONF_DESTINATION,
    CONF_START,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=90)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    opendata = hass.data[DOMAIN][f"{config_entry.entry_id}_opendata_client"]

    start = config.get(CONF_START)
    destination = config.get(CONF_DESTINATION)

    async_add_entities(
        [SwissPublicTransportSensor(opendata, start, destination)],
        update_before_add=True,
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    await hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


class SwissPublicTransportSensor(SensorEntity):
    """Implementation of an Swiss public transport sensor."""

    _attr_attribution = "Data provided by transport.opendata.ch"
    _attr_icon = "mdi:bus"

    def __init__(self, opendata, start, destination):
        """Initialize the sensor."""
        self._opendata = opendata
        self._from = start
        self._to = destination
        self._remaining_time = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{DOMAIN}_{self._from}_{self._to}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return (
            self._opendata.connections[0]["departure"]
            if self._opendata is not None
            else None
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._opendata is None:
            return

        self._remaining_time = dt_util.parse_datetime(
            self._opendata.connections[0]["departure"]
        ) - dt_util.as_local(dt_util.utcnow())

        return {
            ATTR_TRAIN_NUMBER: self._opendata.connections[0]["number"],
            ATTR_PLATFORM: self._opendata.connections[0]["platform"],
            ATTR_TRANSFERS: self._opendata.connections[0]["transfers"],
            ATTR_DURATION: self._opendata.connections[0]["duration"],
            ATTR_DEPARTURE_TIME1: self._opendata.connections[1]["departure"],
            ATTR_DEPARTURE_TIME2: self._opendata.connections[2]["departure"],
            ATTR_START: self._opendata.from_name,
            ATTR_TARGET: self._opendata.to_name,
            ATTR_REMAINING_TIME: f"{self._remaining_time}",
            ATTR_DELAY: self._opendata.connections[0]["delay"],
        }

    async def async_update(self) -> None:
        """Get the latest data from opendata.ch and update the states."""

        try:
            if not self._remaining_time or self._remaining_time.total_seconds() < 0:
                await self._opendata.async_get_data()
        except OpendataTransportError:
            _LOGGER.error("Unable to retrieve data from transport.opendata.ch")
