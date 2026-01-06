"""Support for Tibber binary sensors."""

from __future__ import annotations

import logging

from tibber.data_api import TibberDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TibberConfigEntry
from .coordinator import TibberDataAPICoordinator

_LOGGER = logging.getLogger(__name__)


DATA_API_BINARY_SENSORS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="connector.status",
        translation_key="connector_status",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    BinarySensorEntityDescription(
        key="charging.status",
        translation_key="charging_status",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="onOff",
        translation_key="device_status",
        device_class=BinarySensorDeviceClass.POWER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tibber binary sensors."""
    coordinator = entry.runtime_data.data_api_coordinator
    if coordinator is None:
        return

    entities: list[TibberDataAPIBinarySensor] = []
    api_binary_sensors = {sensor.key: sensor for sensor in DATA_API_BINARY_SENSORS}

    for device in coordinator.data.values():
        for sensor in device.sensors:
            description: BinarySensorEntityDescription | None = api_binary_sensors.get(
                sensor.id
            )
            if description is None:
                continue
            entities.append(TibberDataAPIBinarySensor(coordinator, device, description))
    async_add_entities(entities)


class TibberDataAPIBinarySensor(
    CoordinatorEntity[TibberDataAPICoordinator], BinarySensorEntity
):
    """Representation of a Tibber Data API binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TibberDataAPICoordinator,
        device: TibberDevice,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._device_id: str = device.id
        self.entity_description = entity_description
        self._attr_translation_key = entity_description.translation_key

        self._attr_unique_id = f"{device.external_id}_{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.external_id)},
            name=device.name,
            manufacturer=device.brand,
            model=device.model,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        sensors = self.coordinator.sensors_by_device.get(self._device_id, {})
        sensor = sensors.get(self.entity_description.key)
        if sensor is None:
            return None
        if sensor.value in ("connected", "charging", "on"):
            return True
        if sensor.value in ("disconnected", "idle", "off"):
            return False
        return None
