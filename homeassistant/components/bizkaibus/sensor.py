"""Support for Bizkaibus, Biscay (Basque Country, Spain) Bus service."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_LINE_IDS, CONF_LINES, CONF_STOP_ID, DOMAIN
from .coordinator import ArrivalData, BizkaibusConfigEntry, BizkaibusUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class BizkaibusSensorEntityDescription(SensorEntityDescription):
    """Describes bizkaibus transport sensor entity."""

    value_fn: Callable[[ArrivalData], StateType | datetime]
    icon: str | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BizkaibusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bizkaibus public transport sensor."""

    coordinator = config_entry.runtime_data

    lines_ids = config_entry.options.get(CONF_LINE_IDS, [])
    lines = config_entry.options.get(CONF_LINES, {})

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    selected_unique_ids = {
        f"{config_entry.data[CONF_STOP_ID]}_{line_id}_nearest_arrival"
        for line_id in lines_ids
    }
    obsolete_device_ids: set[str] = set()
    for entity_entry in entity_registry.entities.get_entries_for_config_entry_id(
        config_entry.entry_id
    ):
        if (
            entity_entry.platform == DOMAIN
            and entity_entry.unique_id not in selected_unique_ids
        ):
            if entity_entry.device_id:
                obsolete_device_ids.add(entity_entry.device_id)
            entity_registry.async_remove(entity_entry.entity_id)

    for device_id in obsolete_device_ids:
        if not any(
            entity_entry.device_id == device_id
            for entity_entry in entity_registry.entities.values()
        ):
            device_registry.async_remove_device(device_id)

    if not lines:
        async_add_entities([])
        return

    sensors = [
        BizkaibusSensor(
            coordinator=coordinator,
            entity_description=BizkaibusSensorEntityDescription(
                key="nearest_arrival",
                translation_key="nearest_arrival",
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=lambda x: x.nearest_arrival,
                icon="mdi:bus",
            ),
            line_id=line,
            line_name=lines[line],
        )
        for line in lines_ids
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
        line_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        if not coordinator.config_entry:
            raise ValueError("Config entry data is empty")

        self.line_id = line_id
        self.line_name = line_name

        self._attr_name = f"{self.line_id} {self.line_name}"
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.data[CONF_STOP_ID]}_{line_id}_{entity_description.key}"
        self._attr_icon = entity_description.icon
        unique_id = f"{coordinator.config_entry.data[CONF_STOP_ID]}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        index = self._find_index_by_bus_id()

        if index < 0 or index >= len(self.coordinator.data):
            return None

        self._attr_extra_state_attributes = {
            "next_arrival": self.coordinator.data[index].next_arrival or None
        }
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
    @override
    def available(self) -> bool:
        """Return if sensor is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
