"""Support for Tibber binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

import tibber
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


@dataclass(frozen=True, kw_only=True)
class TibberBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Tibber binary sensor entity."""

    is_on_fn: Callable[[str], bool | None]


DATA_API_BINARY_SENSORS: tuple[TibberBinarySensorEntityDescription, ...] = (
    TibberBinarySensorEntityDescription(
        key="connector.status",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn={"connected": True, "disconnected": False}.get,
    ),
    TibberBinarySensorEntityDescription(
        key="charging.status",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn={"charging": True, "idle": False}.get,
    ),
    TibberBinarySensorEntityDescription(
        key="onOff",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn={"on": True, "off": False}.get,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tibber binary sensors."""
    coordinator = entry.runtime_data.data_api_coordinator
    assert coordinator is not None

    entities: list[TibberDataAPIBinarySensor] = []
    api_binary_sensors = {sensor.key: sensor for sensor in DATA_API_BINARY_SENSORS}

    for device in coordinator.data.values():
        for sensor in device.sensors:
            description: TibberBinarySensorEntityDescription | None = (
                api_binary_sensors.get(sensor.id)
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
    entity_description: TibberBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: TibberDataAPICoordinator,
        device: TibberDevice,
        entity_description: TibberBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._device_id: str = device.id
        self.entity_description = entity_description

        self._attr_unique_id = f"{device.id}_{entity_description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.external_id)},
            name=device.name,
            manufacturer=device.brand,
            model=device.model,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available and self._device_id in self.coordinator.sensors_by_device
        )

    @property
    def device(self) -> dict[str, tibber.data_api.Sensor]:
        """Return the device sensors."""
        return self.coordinator.sensors_by_device[self._device_id]

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.is_on_fn(
            str(self.device[self.entity_description.key].value)
        )
