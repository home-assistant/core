"""Support for Oncue binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import OncueEntity
from .types import OncueConfigEntry

SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="NetworkConnectionEstablished",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)

SENSOR_MAP = {description.key: description for description in SENSOR_TYPES}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OncueConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = config_entry.runtime_data
    devices = coordinator.data
    async_add_entities(
        OncueBinarySensorEntity(coordinator, device_id, device, sensor, SENSOR_MAP[key])
        for device_id, device in devices.items()
        for key, sensor in device.sensors.items()
        if key in SENSOR_MAP
    )


class OncueBinarySensorEntity(OncueEntity, BinarySensorEntity):
    """Representation of an Oncue binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        return self._oncue_value == "true"
