"""Support for Tibber binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True, kw_only=True)
class TibberBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Tibber binary sensor entity."""

    is_on_fn: Callable[[str | None], bool | None]


def _connector_status_is_on(value: str | None) -> bool | None:
    """Map connector status value to binary sensor state."""
    if value == "connected":
        return True
    if value == "disconnected":
        return False
    return None


def _charging_status_is_on(value: str | None) -> bool | None:
    """Map charging status value to binary sensor state."""
    if value == "charging":
        return True
    if value == "idle":
        return False
    return None


def _device_status_is_on(value: str | None) -> bool | None:
    """Map device status value to binary sensor state."""
    if value == "on":
        return True
    if value == "off":
        return False
    return None


DATA_API_BINARY_SENSORS: tuple[TibberBinarySensorEntityDescription, ...] = (
    TibberBinarySensorEntityDescription(
        key="connector.status",
        device_class=BinarySensorDeviceClass.PLUG,
        is_on_fn=_connector_status_is_on,
    ),
    TibberBinarySensorEntityDescription(
        key="charging.status",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        is_on_fn=_charging_status_is_on,
    ),
    TibberBinarySensorEntityDescription(
        key="onOff",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=_device_status_is_on,
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
        assert sensor is not None
        value: str | None = str(sensor.value) if sensor.value is not None else None
        return self.entity_description.is_on_fn(value)
