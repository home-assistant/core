"""Sensors for Clicky Web Analytics."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import device_info
from .const import CONF_SITE_ID
from .coordinator import ClickyConfigEntry, ClickyCoordinator

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="visitorsOnline",
        name="Visitors Online",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="timeTotal",
        name="Total Time Spent",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClickyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Clicky Web Analytics platform."""
    coordinator = entry.runtime_data
    site_id = entry.data[CONF_SITE_ID]

    async_add_entities(
        ClickySensor(
            coordinator=coordinator,
            description=description,
            site_id=site_id,
        )
        for description in SENSOR_TYPES
    )


class ClickySensor(CoordinatorEntity[ClickyCoordinator], SensorEntity):
    """A Clicky sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ClickyCoordinator,
        description: SensorEntityDescription,
        site_id: str,
    ) -> None:
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{site_id}_{description.key}"
        self._attr_device_info = device_info(site_id)

    @property
    @override
    def native_value(self) -> StateType | None:
        """Return the state."""
        return self.coordinator.data[self.entity_description.key]
