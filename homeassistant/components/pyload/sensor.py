"""Support for monitoring pyLoad."""

from __future__ import annotations

from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import PyLoadCoordinator
from .util import api_url


class PyLoadSensorEntity(StrEnum):
    """pyLoad Sensor Entities."""

    ACTIVE = "active"
    QUEUE = "queue"
    TOTAL = "total"
    SPEED = "speed"


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    PyLoadSensorEntity.ACTIVE: SensorEntityDescription(
        key=PyLoadSensorEntity.ACTIVE,
        translation_key=PyLoadSensorEntity.ACTIVE,
    ),
    PyLoadSensorEntity.QUEUE: SensorEntityDescription(
        key=PyLoadSensorEntity.QUEUE,
        translation_key=PyLoadSensorEntity.QUEUE,
    ),
    PyLoadSensorEntity.TOTAL: SensorEntityDescription(
        key=PyLoadSensorEntity.TOTAL,
        translation_key=PyLoadSensorEntity.TOTAL,
    ),
    PyLoadSensorEntity.SPEED: SensorEntityDescription(
        key=PyLoadSensorEntity.SPEED,
        translation_key=PyLoadSensorEntity.SPEED,
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
    ),
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import config from yaml."""

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        PyLoadSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS.values()
    )


class PyLoadSensor(CoordinatorEntity, SensorEntity):
    """Representation of a pyLoad sensor."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: PyLoadCoordinator,
        entity_description: SensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            model=NAME,
            configuration_url=api_url(entry.data),
            identifiers={(DOMAIN, entry.entry_id)},
            translation_key=DOMAIN,
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""
        return self.coordinator.data[self.entity_description.key]
