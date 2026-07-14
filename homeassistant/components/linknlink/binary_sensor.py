"""Binary sensor platform for LinknLink."""

from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LinknLinkConfigEntry, LinknLinkCoordinator
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="pir_detected",
        translation_key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    BinarySensorEntityDescription(
        key="presence",
        translation_key="presence",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LinknLink binary sensors."""
    coordinator = entry.runtime_data
    entities: list[LinknLinkBinarySensor] = [
        LinknLinkBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        LinknLinkBinarySensor(coordinator, description, subdevice_id)
        for subdevice_id, child in coordinator.data.children.items()
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.key in child.fields
    )
    async_add_entities(entities)


class LinknLinkBinarySensor(LinknLinkEntity, BinarySensorEntity):
    """Representation of a LinknLink binary sensor."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: BinarySensorEntityDescription,
        subdevice_id: str | None = None,
    ) -> None:
        """Initialize a LinknLink binary sensor."""
        super().__init__(coordinator, description, subdevice_id)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the sensor is on."""
        return _as_bool(self.source_value)


def _as_bool(value: Any) -> bool | None:
    """Convert a protocol value to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "on", "true", "yes"}:
            return True
        if normalized in {"0", "off", "false", "no"}:
            return False
    return None
