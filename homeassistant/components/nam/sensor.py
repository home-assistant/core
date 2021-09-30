"""Support for the Nettigo Air Monitor service."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import cast

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from . import NAMDataUpdateCoordinator
from .const import ATTR_UPTIME, DOMAIN, MIGRATION_SENSORS, SENSORS

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a Nettigo Air Monitor entities from a config_entry."""
    coordinator: NAMDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Due to the change of the attribute name of two sensors, it is necessary to migrate
    # the unique_ids to the new names.
    ent_reg = entity_registry.async_get(hass)
    for old_sensor, new_sensor in MIGRATION_SENSORS:
        old_unique_id = f"{coordinator.unique_id}-{old_sensor}"
        new_unique_id = f"{coordinator.unique_id}-{new_sensor}"
        if entity_id := ent_reg.async_get_entity_id(PLATFORM, DOMAIN, old_unique_id):
            _LOGGER.debug(
                "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
                entity_id,
                old_unique_id,
                new_unique_id,
            )
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)

    sensors: list[NAMSensor | NAMSensorUptime] = []
    for description in SENSORS:
        if getattr(coordinator.data, description.key) is not None:
            if description.key == ATTR_UPTIME:
                sensors.append(NAMSensorUptime(coordinator, description))
            else:
                sensors.append(NAMSensor(coordinator, description))

    async_add_entities(sensors, False)


class NAMSensor(CoordinatorEntity, SensorEntity):
    """Define an Nettigo Air Monitor sensor."""

    coordinator: NAMDataUpdateCoordinator

    def __init__(
        self,
        coordinator: NAMDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return cast(
            StateType, getattr(self.coordinator.data, self.entity_description.key)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available = super().available

        # For a short time after booting, the device does not return values for all
        # sensors. For this reason, we mark entities for which data is missing as
        # unavailable.
        return (
            available
            and getattr(self.coordinator.data, self.entity_description.key) is not None
        )


class NAMSensorUptime(NAMSensor):
    """Define an Nettigo Air Monitor uptime sensor."""

    @property
    def native_value(self) -> str:
        """Return the state."""
        uptime_sec = getattr(self.coordinator.data, self.entity_description.key)
        return (
            (utcnow() - timedelta(seconds=uptime_sec))
            .replace(microsecond=0)
            .isoformat()
        )
