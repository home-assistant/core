"""Support for IPMA sensors."""
from __future__ import annotations

from dataclasses import dataclass
import logging

import async_timeout
from pyipma.api import IPMA_API
from pyipma.location import Location

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DATA_API, DATA_LOCATION, DOMAIN, MIN_TIME_BETWEEN_UPDATES
from .entity import IPMADevice

_LOGGER = logging.getLogger(__name__)


@dataclass
class IPMARequiredKeysMixin:
    """Mixin for required keys."""

    update_method: str


@dataclass
class IPMASensorEntityDescription(SensorEntityDescription, IPMARequiredKeysMixin):
    """Describes IPMA sensor entity."""


SENSOR_TYPES: tuple[IPMASensorEntityDescription, ...] = (
    IPMASensorEntityDescription(
        key="rcm",
        name="Fire risk",
        translation_key="fire_risk",
        update_method="fire_risk",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the IPMA sensor platform."""
    api = hass.data[DOMAIN][entry.entry_id][DATA_API]
    location = hass.data[DOMAIN][entry.entry_id][DATA_LOCATION]

    entities = [IPMASensor(api, location, description) for description in SENSOR_TYPES]

    async_add_entities(entities, True)


class IPMASensor(SensorEntity, IPMADevice):
    """Representation of an IPMA sensor."""

    entity_description: IPMASensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        api: IPMA_API,
        location: Location,
        description: IPMASensorEntityDescription,
    ) -> None:
        """Initialize the IPMA Sensor."""
        IPMADevice.__init__(self, location)
        self.entity_description = description
        self._api = api
        self._attr_unique_id = f"{self._location.station_latitude}, {self._location.station_longitude}, {self.entity_description.key}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update Fire risk."""
        async with async_timeout.timeout(10):
            if self.entity_description.update_method == "fire_risk":
                rcm = await self._location.fire_risk(self._api)

                if rcm:
                    self._attr_native_value = rcm.rcm
