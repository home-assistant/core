"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_STOP_ID, DOMAIN
from .coordinator import ArrivalData, BizkaibusConfigEntry, BizkaibusUpdateCoordinator


@dataclass(kw_only=True, frozen=True)
class BizkaibusSensorEntityDescription(SensorEntityDescription):
    """Describes bizkaibus transport sensor entity."""

    value_fn: Callable[[ArrivalData], StateType | datetime]
    icon: str | None = None


SENSORS: tuple[BizkaibusSensorEntityDescription, ...] = (
    BizkaibusSensorEntityDescription(
        key="bus_id",
        translation_key="bus_id",
        value_fn=lambda x: x.bus_id,
        icon="mdi:bus-sign",
    ),
    BizkaibusSensorEntityDescription(
        key="bus_name",
        translation_key="bus_name",
        value_fn=lambda x: x.bus_name,
        icon="mdi:bus-stop",
    ),
    BizkaibusSensorEntityDescription(
        key="nearest_arrival",
        translation_key="nearest_arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.nearest_arrival,
        icon="mdi:bus",
    ),
    BizkaibusSensorEntityDescription(
        key="next_arrival",
        translation_key="next_arrival",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.next_arrival,
        icon="mdi:bus-clock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BizkaibusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bizkaibus public transport sensor."""

    coordinator = config_entry.runtime_data

    lines = config_entry.options["lines"]

    sensors = [
        BizkaibusSensor(
            coordinator=coordinator,
            entity_description=SENSORS[2],
            line_id=line,
        )
        for line in lines
    ]

    async_add_entities(sensors)


class BizkaibusSensor(CoordinatorEntity[BizkaibusUpdateCoordinator], SensorEntity):
    """The class for handling the data."""

    line_id: str
    entity_description: BizkaibusSensorEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: BizkaibusUpdateCoordinator,
        entity_description: BizkaibusSensorEntityDescription,
        line_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        if not coordinator.config_entry:
            raise ValueError("Config entry data is empty")

        self.line_id = line_id

        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.data[CONF_STOP_ID]}_{line_id}_{entity_description.key}"
        self._attr_icon = entity_description.icon
        unique_id = f"{coordinator.config_entry.data[CONF_STOP_ID]}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        index = self._find_index_by_bus_id()

        if index < 0 or index >= len(self.coordinator.data):
            return None
        return self.entity_description.value_fn(self.coordinator.data[index])

    def _find_index_by_bus_id(self) -> int:
        """Return the index of the element with the given bus_id, or None if not found."""
        if not self.coordinator.config_entry:
            raise ValueError("Config entry data is empty")

        if not self.coordinator.data:
            return -1
        for idx, item in enumerate(self.coordinator.data):
            if getattr(item, "bus_id", None) == self.line_id:
                return idx
        return -1

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.data is not None
