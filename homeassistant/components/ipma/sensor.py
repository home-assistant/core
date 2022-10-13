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
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DATA_API, DATA_LOCATION, DOMAIN
from .weather import MIN_TIME_BETWEEN_UPDATES

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
        name="Fire Risk",
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


class IPMASensor(SensorEntity):
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
        super().__init__()
        self.entity_description = description
        self._api = api
        self._location = location
        self._value = None

    @property
    def unique_id(self):
        """Return the unique_id."""
        return f"{self._location.station_latitude}, {self._location.station_longitude}, {self.entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    f"{self._location.station_latitude}, {self._location.station_longitude}",
                )
            },
            manufacturer=DOMAIN,
            name=self._location.name,
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update Condition and Forecast."""
        _value = None
        async with async_timeout.timeout(10):
            if self.entity_description.update_method == "fire_risk":
                rcm = await self._location.fire_risk(self._api)
                _value = rcm.rcm

            if _value:
                self._value = _value
            else:
                _LOGGER.warning("Could not update %s", self.entity_description.name)

    @property
    def native_value(self):
        """Return the state."""
        return self._value
