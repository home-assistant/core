"""Support for IPMA sensors."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import asdict, dataclass
import logging
from typing import Any

from pyipma.api import IPMA_API
from pyipma.location import Location
from pyipma.rcm import RCM
from pyipma.uv import UV

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import Throttle

from . import IpmaConfigEntry
from .const import MIN_TIME_BETWEEN_UPDATES
from .entity import IPMADevice

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class IPMASensorEntityDescription(SensorEntityDescription):
    """Describes a IPMA sensor entity."""

    value_fn: Callable[
        [Location, IPMA_API], Coroutine[Location, IPMA_API, tuple[Any, dict[str, Any]]]
    ]


async def async_retrieve_rcm(
    location: Location, api: IPMA_API
) -> tuple[int, dict[str, Any]] | tuple[None, dict[str, Any]]:
    """Retrieve RCM."""
    fire_risk: RCM = await location.fire_risk(api)
    if fire_risk:
        return fire_risk.rcm, {}
    return None, {}


async def async_retrieve_uvi(
    location: Location, api: IPMA_API
) -> tuple[int, dict[str, Any]] | tuple[None, dict[str, Any]]:
    """Retrieve UV."""
    uv_risk: UV = await location.uv_risk(api)
    if uv_risk:
        return round(uv_risk.iUv), {}
    return None, {}


async def async_retrieve_warning(
    location: Location, api: IPMA_API
) -> tuple[Any, dict[str, str]]:
    """Retrieve Warning."""
    warnings = await location.warnings(api)
    if len(warnings):
        return warnings[0].awarenessLevelID, {
            k: str(v) for k, v in asdict(warnings[0]).items()
        }
    return "green", {}


SENSOR_TYPES: tuple[IPMASensorEntityDescription, ...] = (
    IPMASensorEntityDescription(
        key="rcm",
        translation_key="fire_risk",
        value_fn=async_retrieve_rcm,
    ),
    IPMASensorEntityDescription(
        key="uvi",
        translation_key="uv_index",
        value_fn=async_retrieve_uvi,
    ),
    IPMASensorEntityDescription(
        key="alert",
        translation_key="weather_alert",
        value_fn=async_retrieve_warning,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IpmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the IPMA sensor platform."""
    location = entry.runtime_data.location
    api = entry.runtime_data.api

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
        IPMADevice.__init__(self, api, location)
        self.entity_description = description
        self._attr_unique_id = f"{self._location.station_latitude}, {self._location.station_longitude}, {self.entity_description.key}"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update sensors."""
        async with asyncio.timeout(10):
            state, attrs = await self.entity_description.value_fn(
                self._location, self._api
            )
            self._attr_native_value = state
            self._attr_extra_state_attributes = attrs
