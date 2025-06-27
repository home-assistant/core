"""Support for De Lijn (Flemish public transport) information."""

from __future__ import annotations

from datetime import datetime
import logging

from pydelijn.api import Passages
from pydelijn.common import HttpException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by data.delijn.be"

CONF_NEXT_DEPARTURE = "next_departure"
CONF_STOP_ID = "stop_id"
CONF_NUMBER_OF_DEPARTURES = "number_of_departures"

DEFAULT_NAME = "De Lijn"

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STOP_ID): cv.string,
                vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int,
            }
        ],
    }
)

AUTO_ATTRIBUTES = (
    "line_number_public",
    "line_transport_type",
    "final_destination",
    "due_at_schedule",
    "due_at_realtime",
    "is_realtime",
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create the sensor."""
    api_key = config[CONF_API_KEY]

    session = async_get_clientsession(hass)

    async_add_entities(
        (
            DeLijnPublicTransportSensor(
                Passages(
                    nextpassage[CONF_STOP_ID],
                    nextpassage[CONF_NUMBER_OF_DEPARTURES],
                    api_key,
                    session,
                    True,
                )
            )
            for nextpassage in config[CONF_NEXT_DEPARTURE]
        ),
        True,
    )


class DeLijnPublicTransportSensor(SensorEntity):
    """Representation of a Ruter sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus"

    def __init__(self, line):
        """Initialize the sensor."""
        self.line = line
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Get the latest data from the De Lijn API."""
        try:
            await self.line.get_passages()
            self._attr_name = await self.line.get_stopname()
        except HttpException:
            self._attr_available = False
            _LOGGER.error("De Lijn http error")
            return

        self._attr_extra_state_attributes["stopname"] = self._attr_name

        if not self.line.passages:
            self._attr_available = False
            return

        try:
            first = self.line.passages[0]
            if (first_passage := first["due_at_realtime"]) is None:
                first_passage = first["due_at_schedule"]
            self._attr_native_value = datetime.strptime(
                first_passage, "%Y-%m-%dT%H:%M:%S%z"
            )

            for key in AUTO_ATTRIBUTES:
                self._attr_extra_state_attributes[key] = first[key]
            self._attr_extra_state_attributes["next_passages"] = self.line.passages

            self._attr_available = True
        except KeyError as error:
            _LOGGER.error("Invalid data received from De Lijn: %s", error)
            self._attr_available = False
