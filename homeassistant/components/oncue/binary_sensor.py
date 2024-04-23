"""Support for Oncue binary sensors."""

from __future__ import annotations

from aiooncue import OncueDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import OncueEntity

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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: DataUpdateCoordinator[dict[str, OncueDevice]] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities: list[OncueBinarySensorEntity] = []
    devices = coordinator.data
    for device_id, device in devices.items():
        entities.extend(
            OncueBinarySensorEntity(
                coordinator, device_id, device, sensor, SENSOR_MAP[key]
            )
            for key, sensor in device.sensors.items()
            if key in SENSOR_MAP
        )

    async_add_entities(entities)


class OncueBinarySensorEntity(OncueEntity, BinarySensorEntity):
    """Representation of an Oncue binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the binary sensor state."""
        return self._oncue_value == "true"
