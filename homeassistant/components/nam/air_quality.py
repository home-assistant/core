"""Support for the Nettigo Air Monitor air_quality service."""
from __future__ import annotations

import logging
from typing import Union, cast

from homeassistant.components.air_quality import DOMAIN as PLATFORM, AirQualityEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NAMDataUpdateCoordinator
from .const import (
    AIR_QUALITY_SENSORS,
    ATTR_SDS011,
    DEFAULT_NAME,
    DOMAIN,
    SUFFIX_P1,
    SUFFIX_P2,
)

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator: NAMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of one sensor, it is necessary to migrate
    # the unique_id to the new name.
    ent_reg = entity_registry.async_get(hass)
    old_unique_id = f"{coordinator.unique_id}-sds"
    new_unique_id = f"{coordinator.unique_id}-{ATTR_SDS011}"
    if entity_id := ent_reg.async_get_entity_id(PLATFORM, DOMAIN, old_unique_id):
        _LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)

    entities: list[NAMAirQuality] = []
    for sensor in AIR_QUALITY_SENSORS:
        if getattr(coordinator.data, f"{sensor}{SUFFIX_P1}") is not None:
            entities.append(NAMAirQuality(coordinator, sensor))

    async_add_entities(entities, False)


class NAMAirQuality(CoordinatorEntity, AirQualityEntity):
    """Define an Nettigo Air Monitor air quality."""

    coordinator: NAMDataUpdateCoordinator

    def __init__(self, coordinator: NAMDataUpdateCoordinator, sensor_type: str) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_name = f"{DEFAULT_NAME} {AIR_QUALITY_SENSORS[sensor_type]}"
        self._attr_unique_id = f"{coordinator.unique_id}-{sensor_type}"
        self.sensor_type = sensor_type

    @property
    def particulate_matter_2_5(self) -> int | None:
        """Return the particulate matter 2.5 level."""
        return cast(
            Union[int, None],
            getattr(self.coordinator.data, f"{self.sensor_type}{SUFFIX_P2}"),
        )

    @property
    def particulate_matter_10(self) -> int | None:
        """Return the particulate matter 10 level."""
        return cast(
            Union[int, None],
            getattr(self.coordinator.data, f"{self.sensor_type}{SUFFIX_P1}"),
        )

    @property
    def carbon_dioxide(self) -> int | None:
        """Return the particulate matter 10 level."""
        return cast(Union[int, None], self.coordinator.data.mhz14a_carbon_dioxide)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return (
            available
            and getattr(self.coordinator.data, f"{self.sensor_type}{SUFFIX_P2}")
            is not None
        )
